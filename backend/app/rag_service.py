import os
import json
import httpx
from typing import List, Optional, Set
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
