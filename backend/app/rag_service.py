import os
import json
import httpx
import time
import logging
from typing import List, Optional, Set, Dict, Any
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue, MatchAny
)
from app.config import get_settings
from app.models import TelegramMessage, RAGResult, RAGSource, ContactInfo


COLLECTION_EMBEDDINGS = "telegram_embeddings"
COLLECTION_MESSAGES = "telegram_messages"
COLLECTION_CONTACTS = "telegram_contacts"
COLLECTION_CONTACTS_EMBEDDINGS = "telegram_contacts_embeddings"


class RAGService:
    def __init__(self):
        self.settings = get_settings()
        self.qdrant = QdrantClient(
            host=self.settings.qdrant_host,
            port=self.settings.qdrant_port
        )
        self.embedding_dim = 1536  # text-embedding-3-small
        self._ensure_collections()
        self._known_contacts: Set[int] = set()
        self._load_known_contacts()
        self.logger = logging.getLogger("rag_answer")

    def _ensure_collections(self):
        collections = [c.name for c in self.qdrant.get_collections().collections]
        
        if COLLECTION_EMBEDDINGS not in collections:
            self.qdrant.create_collection(
                collection_name=COLLECTION_EMBEDDINGS,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )
        
        if COLLECTION_MESSAGES not in collections:
            self.qdrant.create_collection(
                collection_name=COLLECTION_MESSAGES,
                vectors_config=VectorParams(
                    size=1,  # dummy vector
                    distance=Distance.COSINE
                )
            )
        
        if COLLECTION_CONTACTS not in collections:
            self.qdrant.create_collection(
                collection_name=COLLECTION_CONTACTS,
                vectors_config=VectorParams(
                    size=1,  # dummy vector
                    distance=Distance.COSINE
                )
            )
        
        if COLLECTION_CONTACTS_EMBEDDINGS not in collections:
            self.qdrant.create_collection(
                collection_name=COLLECTION_CONTACTS_EMBEDDINGS,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )

    def _load_known_contacts(self):
        """Загрузить ID известных контактов"""
        try:
            scroll_result = self.qdrant.scroll(
                collection_name=COLLECTION_CONTACTS,
                limit=10000,
                with_payload=True,
                with_vectors=False
            )
            for point in scroll_result[0]:
                user_id = point.payload.get("user_id")
                if user_id:
                    self._known_contacts.add(user_id)
        except:
            pass

    def is_contact_known(self, user_id: int) -> bool:
        return user_id in self._known_contacts

    def add_contact(self, contact: ContactInfo) -> bool:
        """Добавить контакт в базу с индексацией bio"""
        try:
            contact_data = contact.model_dump()
            if contact.updated_at:
                contact_data['updated_at'] = contact.updated_at.isoformat()
            
            # Сохраняем контакт
            self.qdrant.upsert(
                collection_name=COLLECTION_CONTACTS,
                points=[PointStruct(
                    id=contact.id % (2**63),
                    vector=[0.0],
                    payload={
                        "user_id": contact.id,
                        "username": contact.username,
                        "full_name": contact.full_name,
                        "contact_json": json.dumps(contact_data, ensure_ascii=False)
                    }
                )]
            )
            
            # Индексируем bio для поиска
            if contact.bio:
                # Создаём текст для индексации: имя + username + bio
                index_text = f"{contact.full_name}"
                if contact.username:
                    index_text += f" @{contact.username}"
                index_text += f" {contact.bio}"
                
                embedding = self._get_embedding(index_text)
                
                self.qdrant.upsert(
                    collection_name=COLLECTION_CONTACTS_EMBEDDINGS,
                    points=[PointStruct(
                        id=contact.id % (2**63),
                        vector=embedding,
                        payload={
                            "user_id": contact.id,
                            "username": contact.username,
                            "full_name": contact.full_name,
                            "bio": contact.bio,
                            "has_channel": contact.personal_channel_id is not None
                        }
                    )]
                )
            
            self._known_contacts.add(contact.id)
            return True
        except Exception as e:
            print(f"Error adding contact: {e}")
            return False

    def get_contact(self, user_id: int) -> Optional[ContactInfo]:
        """Получить контакт из базы"""
        try:
            points = self.qdrant.retrieve(
                collection_name=COLLECTION_CONTACTS,
                ids=[user_id % (2**63)],
                with_payload=True
            )
            if points:
                data = json.loads(points[0].payload["contact_json"])
                if data.get('updated_at'):
                    data['updated_at'] = datetime.fromisoformat(data['updated_at'])
                return ContactInfo(**data)
        except:
            pass
        return None

    def get_all_contacts(self) -> List[ContactInfo]:
        """Получить все контакты"""
        contacts = []
        try:
            scroll_result = self.qdrant.scroll(
                collection_name=COLLECTION_CONTACTS,
                limit=10000,
                with_payload=True,
                with_vectors=False
            )
            for point in scroll_result[0]:
                data = json.loads(point.payload["contact_json"])
                if data.get('updated_at'):
                    data['updated_at'] = datetime.fromisoformat(data['updated_at'])
                contacts.append(ContactInfo(**data))
        except:
            pass
        return contacts

    async def search_contacts(
        self,
        query: str,
        top_k: int = 20,
        expand_query: bool = True
    ) -> List[dict]:
        """Поиск контактов по bio"""
        search_query = query
        if expand_query:
            try:
                search_query = self._expand_query(query)
            except:
                pass
        
        query_embedding = self._get_embedding(search_query)
        
        results = self.qdrant.search(
            collection_name=COLLECTION_CONTACTS_EMBEDDINGS,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True
        )
        
        contact_results = []
        for result in results:
            user_id = result.payload.get("user_id")
            contact = self.get_contact(user_id)
            if contact:
                contact_results.append({
                    "contact": contact,
                    "score": result.score
                })
        
        return contact_results

    def get_contact_messages_count(self, user_id: int) -> int:
        """Получить количество сообщений от контакта"""
        try:
            # Считаем сообщения этого автора
            scroll_result = self.qdrant.scroll(
                collection_name=COLLECTION_EMBEDDINGS,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="author_id",
                            match=MatchValue(value=user_id)
                        )
                    ]
                ),
                limit=10000,
                with_payload=False,
                with_vectors=False
            )
            return len(scroll_result[0])
        except:
            return 0

    def get_new_contact_ids(self, author_ids: List[int]) -> List[int]:
        """Вернуть ID контактов которых нет в базе"""
        return [uid for uid in author_ids if uid and uid not in self._known_contacts]

    def _get_embedding(self, text: str) -> List[float]:
        """Получить эмбеддинг через OpenAI API"""
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.settings.embedding_model,
                    "input": text
                }
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Получить эмбеддинги для батча текстов"""
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.settings.embedding_model,
                    "input": texts
                }
            )
            response.raise_for_status()
            data = response.json()["data"]
            return [item["embedding"] for item in data]

    def _expand_query(self, query: str) -> str:
        """Расширить запрос ключевыми словами для лучшего поиска"""
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": """Ты помощник для поиска по базе сообщений из Telegram чатов.
Твоя задача - расширить поисковый запрос пользователя ключевыми словами и фразами,
которые могут встречаться в релевантных сообщениях.

Правила:
1. Добавь синонимы и связанные термины
2. Добавь конкретные слова которые люди используют в таких сообщениях
3. Учитывай что это русскоязычные чаты
4. Верни ТОЛЬКО расширенный запрос без объяснений
5. Не более 100 слов"""
                        },
                        {
                            "role": "user", 
                            "content": f"Расширь запрос: {query}"
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200
                }
            )
            response.raise_for_status()
            expanded = response.json()["choices"][0]["message"]["content"]
            return f"{query} {expanded}"

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _build_canonical_documents(
        self,
        results: List[RAGResult],
        min_text_length: int = 20,
        max_tokens: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        seen_msg_ids: Set[int] = set()
        documents: List[Dict[str, Any]] = []
        tokens_used = 0
        limit = max_tokens or self.settings.rag_answer_context_tokens

        for result in results:
            message = result.message
            if message.id in seen_msg_ids:
                continue
            if not message.text or len(message.text.strip()) < min_text_length:
                continue

            doc_tokens = self._estimate_tokens(message.text)
            if tokens_used + doc_tokens > limit:
                break

            seen_msg_ids.add(message.id)
            tokens_used += doc_tokens

            author_name_parts = [message.author.first_name or "", message.author.last_name or ""]
            author_name = " ".join(p for p in author_name_parts if p).strip() or None
            username = f"@{message.author.username}" if message.author.username else None
            chat_tags = [message.topic_title] if message.topic_title else []

            documents.append({
                "cid": len(documents) + 1,
                "platform": "telegram",
                "chat_id": message.chat_id,
                "chat_title": message.chat_title,
                "chat_tags": chat_tags,
                "username": username,
                "author_name": author_name,
                "msg_id": message.id,
                "date": message.date.isoformat(),
                "score": result.score,
                "text": message.text,
                "tg_link": message.telegram_link
            })

        return documents

    def _build_answer_prompt(self, query: str, documents: List[Dict[str, Any]], answer_style: str) -> List[Dict[str, str]]:
        style_note = "короткий" if answer_style == "brief" else "стандартный"
        schema = """{
  "summary": "string",
  "sections": [
    {
      "title": "string",
      "items": [
        {
          "lead": {
            "username": "@username",
            "who": "string",
            "intent": "string",
            "need": "string"
          },
          "why_fit": ["string"],
          "next_step": "string",
          "citations": [1]
        }
      ]
    }
  ],
  "rejected": [
    {
      "reason": "string",
      "citations": [2]
    }
  ]
}"""
        system_message = (
            "Ты — Answer Composer для лидогенерации. "
            "Твоя задача — синтезировать ответ по сообщениям из Telegram. "
            "Отвечай строго JSON по схеме. Используй только citations из cid документов. "
            "Нельзя выдумывать факты. Опирайся на поле text. "
            "Группируй в 3–6 секций, если есть данные. "
            "Для каждого кандидата обязательно: why_fit и next_step (1 фраза). "
            "Отдельно массив rejected для нерелевантных/специалистов. "
            "Если данных недостаточно — создай секцию 'Нужны уточнения' с вопросами и citations. "
            f"Стиль ответа: {style_note}."
        )
        user_message = (
            "Запрос пользователя:\n"
            f"{query}\n\n"
            "Документы (канонический JSON):\n"
            f"{json.dumps(documents, ensure_ascii=False)}\n\n"
            "Схема ответа (JSON):\n"
            f"{schema}"
        )
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

    def _build_repair_prompt(self, content: str) -> List[Dict[str, str]]:
        system_message = (
            "Ты — JSON repair assistant. "
            "Приведи вывод к строгому JSON по указанной схеме. "
            "Не добавляй комментариев или текста вне JSON."
        )
        user_message = (
            "Исправь следующий ответ в валидный JSON по схеме:\n"
            f"{content}"
        )
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

    def _call_chat_completion(self, messages: List[Dict[str, str]]) -> str:
        with httpx.Client(timeout=40.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.settings.rag_answer_model,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 1200,
                    "response_format": {"type": "json_object"}
                }
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    def _build_answer_markdown(self, answer_payload: Dict[str, Any]) -> str:
        summary = answer_payload.get("summary", "")
        sections = answer_payload.get("sections", [])
        rejected = answer_payload.get("rejected", [])
        lines: List[str] = []
        if summary:
            lines.append(summary)
            lines.append("")
        for section in sections:
            title = section.get("title") or "Секция"
            lines.append(f"### {title}")
            for item in section.get("items", []):
                lead = item.get("lead", {})
                username = lead.get("username") or lead.get("who") or "Кандидат"
                need = lead.get("need") or lead.get("intent") or ""
                why_fit = "; ".join(item.get("why_fit") or [])
                next_step = item.get("next_step") or ""
                citations = item.get("citations") or []
                citation_text = "".join([f"[{cid}]" for cid in citations])
                parts = [f"**{username}**"]
                if need:
                    parts.append(need)
                if why_fit:
                    parts.append(why_fit)
                if next_step:
                    parts.append(f"Дальше: {next_step}")
                if citation_text:
                    parts.append(citation_text)
                lines.append(f"- {' — '.join(parts)}")
            lines.append("")
        if rejected:
            lines.append("### Не подошли")
            for item in rejected:
                reason = item.get("reason") or "Не подходит"
                citations = item.get("citations") or []
                citation_text = "".join([f"[{cid}]" for cid in citations])
                lines.append(f"- {reason} {citation_text}".strip())
        return "\n".join(lines).strip()

    def _validate_answer_citations(self, answer_payload: Dict[str, Any], max_cid: int) -> Dict[str, Any]:
        def normalize_citations(values: Any) -> List[int]:
            if not isinstance(values, list):
                return []
            valid = []
            for cid in values:
                if isinstance(cid, int) and 1 <= cid <= max_cid:
                    valid.append(cid)
            return list(dict.fromkeys(valid))

        sections = answer_payload.get("sections", [])
        validated_sections = []
        for section in sections:
            items = section.get("items", [])
            validated_items = []
            for item in items:
                citations = normalize_citations(item.get("citations"))
                if not citations:
                    continue
                item["citations"] = citations
                validated_items.append(item)
            if validated_items:
                section["items"] = validated_items
                validated_sections.append(section)

        rejected = answer_payload.get("rejected", [])
        validated_rejected = []
        for item in rejected:
            citations = normalize_citations(item.get("citations"))
            if not citations:
                continue
            item["citations"] = citations
            validated_rejected.append(item)

        answer_payload["sections"] = validated_sections
        answer_payload["rejected"] = validated_rejected
        return answer_payload

    async def generate_answer(
        self,
        query: str,
        chat_ids: List[int],
        top_k: int = 20,
        answer_style: str = "standard",
        min_text_length: int = 20,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_score: Optional[float] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        results = await self.search(
            query=query,
            chat_ids=chat_ids,
            top_k=top_k,
            min_text_length=min_text_length,
            expand_query=True
        )

        filtered_results: List[RAGResult] = []
        for result in results:
            message_date = result.message.date
            if date_from and message_date < date_from:
                continue
            if date_to and message_date > date_to:
                continue
            if min_score is not None and result.score < min_score:
                continue
            filtered_results.append(result)

        documents = self._build_canonical_documents(filtered_results, min_text_length=min_text_length)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        if not documents:
            return {
                "answer": {
                    "summary": "Недостаточно данных для сводки по выбранным источникам.",
                    "sections": [],
                    "rejected": [],
                    "markdown": "Недостаточно данных для сводки по выбранным источникам."
                },
                "citations": [],
                "retrieval": {"topK": top_k, "used": 0, "latencyMs": latency_ms},
                "error": None
            }

        raw_content = ""
        try:
            prompt = self._build_answer_prompt(query, documents, answer_style)
            raw_content = self._call_chat_completion(prompt)
            answer_payload = json.loads(raw_content)
        except Exception:
            try:
                repair_prompt = self._build_repair_prompt(raw_content)
                repaired = self._call_chat_completion(repair_prompt)
                answer_payload = json.loads(repaired)
            except Exception as repair_error:
                self.logger.warning("RAG answer JSON repair failed: %s", repair_error)
                return {
                    "answer": None,
                    "citations": [],
                    "retrieval": {"topK": top_k, "used": len(documents), "latencyMs": latency_ms},
                    "error": "invalid_json"
                }

        answer_payload = self._validate_answer_citations(answer_payload, max_cid=len(documents))
        markdown = self._build_answer_markdown(answer_payload)
        answer_payload["markdown"] = markdown

        citations = []
        for doc in documents:
            citations.append({
                "cid": doc["cid"],
                "platform": doc["platform"],
                "chat_id": doc.get("chat_id"),
                "chat_title": doc.get("chat_title"),
                "username": doc.get("username"),
                "author_name": doc.get("author_name"),
                "message_id": doc.get("msg_id"),
                "date": doc.get("date"),
                "score": doc.get("score"),
                "text": doc.get("text"),
                "tg_link": doc.get("tg_link")
            })

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        self.logger.info(
            "RAG answer query=%s topK=%s used=%s latencyMs=%s",
            query, top_k, len(documents), latency_ms
        )
        self.logger.info("RAG answer docs: %s", [doc["msg_id"] for doc in documents])
        self.logger.info("RAG answer payload: %s", json.dumps(answer_payload, ensure_ascii=False))

        return {
            "answer": answer_payload,
            "citations": citations,
            "retrieval": {"topK": top_k, "used": len(documents), "latencyMs": latency_ms},
            "error": None
        }

    def _message_to_point_id(self, chat_id: int, message_id: int, topic_id: Optional[int] = None) -> str:
        if topic_id:
            return f"{chat_id}_{topic_id}_{message_id}"
        return f"{chat_id}_{message_id}"

    async def index_message(self, message: TelegramMessage) -> bool:
        try:
            point_id = self._message_to_point_id(
                message.chat_id, 
                message.id, 
                message.topic_id
            )
            
            message_data = message.model_dump()
            message_data['date'] = message.date.isoformat()
            
            self.qdrant.upsert(
                collection_name=COLLECTION_MESSAGES,
                points=[PointStruct(
                    id=hash(point_id) % (2**63),
                    vector=[0.0],
                    payload={
                        "point_id": point_id,
                        "chat_id": message.chat_id,
                        "chat_title": message.chat_title,
                        "chat_username": message.chat_username,
                        "topic_id": message.topic_id,
                        "topic_title": message.topic_title,
                        "message_id": message.id,
                        "message_json": json.dumps(message_data, ensure_ascii=False)
                    }
                )]
            )
            
            embedding = self._get_embedding(message.text)
            
            self.qdrant.upsert(
                collection_name=COLLECTION_EMBEDDINGS,
                points=[PointStruct(
                    id=hash(point_id) % (2**63),
                    vector=embedding,
                    payload={
                        "point_id": point_id,
                        "chat_id": message.chat_id,
                        "chat_title": message.chat_title,
                        "chat_username": message.chat_username,
                        "topic_id": message.topic_id,
                        "topic_title": message.topic_title,
                        "message_id": message.id,
                        "author_id": message.author.id,
                        "author_username": message.author.username,
                        "text": message.text[:500],
                        "text_length": len(message.text),
                        "date": message.date.isoformat()
                    }
                )]
            )
            
            return True
        except Exception as e:
            print(f"Error indexing message: {e}")
            return False

    async def index_messages_batch(self, messages: List[TelegramMessage]) -> int:
        indexed = 0
        
        batch_size = 100
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i+batch_size]
            
            try:
                texts = [m.text for m in batch]
                embeddings = self._get_embeddings_batch(texts)
                
                embedding_points = []
                message_points = []
                
                for j, (message, embedding) in enumerate(zip(batch, embeddings)):
                    point_id = self._message_to_point_id(
                        message.chat_id,
                        message.id,
                        message.topic_id
                    )
                    numeric_id = hash(point_id) % (2**63)
                    
                    message_data = message.model_dump()
                    message_data['date'] = message.date.isoformat()
                    
                    message_points.append(PointStruct(
                        id=numeric_id,
                        vector=[0.0],
                        payload={
                            "point_id": point_id,
                            "chat_id": message.chat_id,
                            "chat_title": message.chat_title,
                            "chat_username": message.chat_username,
                            "topic_id": message.topic_id,
                            "topic_title": message.topic_title,
                            "message_id": message.id,
                            "message_json": json.dumps(message_data, ensure_ascii=False)
                        }
                    ))
                    
                    embedding_points.append(PointStruct(
                        id=numeric_id,
                        vector=embedding,
                        payload={
                            "point_id": point_id,
                            "chat_id": message.chat_id,
                            "chat_title": message.chat_title,
                            "chat_username": message.chat_username,
                            "topic_id": message.topic_id,
                            "topic_title": message.topic_title,
                            "message_id": message.id,
                            "author_id": message.author.id,
                            "author_username": message.author.username,
                            "text": message.text[:500],
                            "text_length": len(message.text),
                            "date": message.date.isoformat()
                        }
                    ))
                
                self.qdrant.upsert(
                    collection_name=COLLECTION_MESSAGES,
                    points=message_points
                )
                self.qdrant.upsert(
                    collection_name=COLLECTION_EMBEDDINGS,
                    points=embedding_points
                )
                
                indexed += len(batch)
                
            except Exception as e:
                print(f"Error in batch indexing: {e}")
                for message in batch:
                    if await self.index_message(message):
                        indexed += 1
        
        return indexed

    async def search(
        self, 
        query: str, 
        chat_ids: List[int], 
        top_k: int = 10,
        min_text_length: int = 50,
        expand_query: bool = True
    ) -> List[RAGResult]:
        # Расширяем запрос для лучшего поиска
        search_query = query
        if expand_query:
            try:
                search_query = self._expand_query(query)
                print(f"Expanded query: {search_query[:200]}...")
            except Exception as e:
                print(f"Query expansion failed: {e}")
        
        query_embedding = self._get_embedding(search_query)
        
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="chat_id",
                    match=MatchAny(any=chat_ids)
                )
            ]
        )
        
        # Запрашиваем больше результатов для фильтрации
        results = self.qdrant.search(
            collection_name=COLLECTION_EMBEDDINGS,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=top_k * 3,
            with_payload=True
        )
        
        rag_results = []
        for result in results:
            # Фильтруем короткие сообщения
            text_length = result.payload.get("text_length", 0)
            if text_length < min_text_length:
                continue
            
            point_id = result.payload.get("point_id")
            numeric_id = hash(point_id) % (2**63)
            
            message_points = self.qdrant.retrieve(
                collection_name=COLLECTION_MESSAGES,
                ids=[numeric_id],
                with_payload=True
            )
            
            if message_points:
                message_json = message_points[0].payload.get("message_json")
                message_data = json.loads(message_json)
                message_data['date'] = datetime.fromisoformat(message_data['date'])
                
                rag_results.append(RAGResult(
                    message=TelegramMessage(**message_data),
                    score=result.score,
                    highlight=result.payload.get("text")
                ))
            
            if len(rag_results) >= top_k:
                break
        
        return rag_results

    def get_available_sources(self) -> List[RAGSource]:
        sources = {}
        
        scroll_result = self.qdrant.scroll(
            collection_name=COLLECTION_EMBEDDINGS,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )
        
        for point in scroll_result[0]:
            chat_id = point.payload.get("chat_id")
            chat_title = point.payload.get("chat_title")
            topic_id = point.payload.get("topic_id")
            topic_title = point.payload.get("topic_title")
            
            key = f"{chat_id}_{topic_id}" if topic_id else str(chat_id)
            
            if key not in sources:
                sources[key] = RAGSource(
                    chat_id=chat_id,
                    chat_title=chat_title,
                    topic_id=topic_id,
                    topic_title=topic_title,
                    messages_count=0
                )
            sources[key].messages_count += 1
        
        return list(sources.values())

    def get_all_messages(self) -> List[dict]:
        """Получить все сообщения из базы"""
        messages = []
        offset = None

        while True:
            scroll_result = self.qdrant.scroll(
                collection_name=COLLECTION_MESSAGES,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            points, next_offset = scroll_result

            for point in points:
                message_json = point.payload.get("message_json")
                if message_json:
                    message_data = json.loads(message_json)
                    messages.append(message_data)

            if next_offset is None:
                break
            offset = next_offset

        return messages

    def get_stats(self) -> dict:
        try:
            emb_info = self.qdrant.get_collection(COLLECTION_EMBEDDINGS)
            msg_info = self.qdrant.get_collection(COLLECTION_MESSAGES)
            contacts_info = self.qdrant.get_collection(COLLECTION_CONTACTS)
            
            return {
                "embeddings_count": emb_info.points_count,
                "messages_count": msg_info.points_count,
                "contacts_count": contacts_info.points_count,
                "sources": len(self.get_available_sources())
            }
        except Exception as e:
            return {"error": str(e)}

    def delete_source(self, chat_id: int, topic_id: Optional[int] = None) -> dict:
        """Удалить источник (чат/топик) из базы"""
        try:
            deleted_embeddings = 0
            deleted_messages = 0
            
            # Формируем фильтр
            filter_conditions = [
                FieldCondition(
                    key="chat_id",
                    match=MatchValue(value=chat_id)
                )
            ]
            
            if topic_id is not None:
                filter_conditions.append(
                    FieldCondition(
                        key="topic_id",
                        match=MatchValue(value=topic_id)
                    )
                )
            
            delete_filter = Filter(must=filter_conditions)
            
            # Считаем сколько удалим
            scroll_result = self.qdrant.scroll(
                collection_name=COLLECTION_EMBEDDINGS,
                scroll_filter=delete_filter,
                limit=10000,
                with_payload=False,
                with_vectors=False
            )
            deleted_embeddings = len(scroll_result[0])
            
            # Удаляем из embeddings
            self.qdrant.delete(
                collection_name=COLLECTION_EMBEDDINGS,
                points_selector=delete_filter
            )
            
            # Удаляем из messages
            self.qdrant.delete(
                collection_name=COLLECTION_MESSAGES,
                points_selector=delete_filter
            )
            
            return {
                "success": True,
                "deleted_embeddings": deleted_embeddings,
                "deleted_messages": deleted_embeddings,
                "chat_id": chat_id,
                "topic_id": topic_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


rag_service = RAGService()
