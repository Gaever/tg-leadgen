import os
import json
from typing import List, Optional
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue, MatchAny
)
from openai import OpenAI
from app.config import get_settings
from app.models import TelegramMessage, RAGResult, RAGSource


COLLECTION_EMBEDDINGS = "telegram_embeddings"
COLLECTION_MESSAGES = "telegram_messages"


class RAGService:
    def __init__(self):
        self.settings = get_settings()
        self.qdrant = QdrantClient(
            host=self.settings.qdrant_host,
            port=self.settings.qdrant_port
        )
        self.openai = OpenAI(api_key=self.settings.openai_api_key)
        self.embedding_dim = 1536  # text-embedding-3-small
        self._ensure_collections()

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
                    size=1,  # dummy vector for storage-only collection
                    distance=Distance.COSINE
                )
            )

    def _get_embedding(self, text: str) -> List[float]:
        response = self.openai.embeddings.create(
            model=self.settings.embedding_model,
            input=text
        )
        return response.data[0].embedding

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
            
            # Store original message as JSON
            message_data = message.model_dump()
            message_data['date'] = message.date.isoformat()
            
            self.qdrant.upsert(
                collection_name=COLLECTION_MESSAGES,
                points=[PointStruct(
                    id=hash(point_id) % (2**63),
                    vector=[0.0],  # dummy vector
                    payload={
                        "point_id": point_id,
                        "chat_id": message.chat_id,
                        "chat_title": message.chat_title,
                        "topic_id": message.topic_id,
                        "topic_title": message.topic_title,
                        "message_id": message.id,
                        "message_json": json.dumps(message_data, ensure_ascii=False)
                    }
                )]
            )
            
            # Create embedding and store
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
                        "topic_id": message.topic_id,
                        "topic_title": message.topic_title,
                        "message_id": message.id,
                        "author_id": message.author.id,
                        "author_username": message.author.username,
                        "text": message.text[:500],  # Store truncated for display
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
        
        # Batch embeddings for efficiency
        batch_size = 100
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i+batch_size]
            
            try:
                texts = [m.text for m in batch]
                response = self.openai.embeddings.create(
                    model=self.settings.embedding_model,
                    input=texts
                )
                
                embedding_points = []
                message_points = []
                
                for j, (message, emb_data) in enumerate(zip(batch, response.data)):
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
                            "topic_id": message.topic_id,
                            "topic_title": message.topic_title,
                            "message_id": message.id,
                            "message_json": json.dumps(message_data, ensure_ascii=False)
                        }
                    ))
                    
                    embedding_points.append(PointStruct(
                        id=numeric_id,
                        vector=emb_data.embedding,
                        payload={
                            "point_id": point_id,
                            "chat_id": message.chat_id,
                            "chat_title": message.chat_title,
                            "topic_id": message.topic_id,
                            "topic_title": message.topic_title,
                            "message_id": message.id,
                            "author_id": message.author.id,
                            "author_username": message.author.username,
                            "text": message.text[:500],
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
                # Fall back to individual indexing
                for message in batch:
                    if await self.index_message(message):
                        indexed += 1
        
        return indexed

    async def search(
        self, 
        query: str, 
        chat_ids: List[int], 
        top_k: int = 10
    ) -> List[RAGResult]:
        query_embedding = self._get_embedding(query)
        
        # Build filter for selected chats
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="chat_id",
                    match=MatchAny(any=chat_ids)
                )
            ]
        )
        
        results = self.qdrant.search(
            collection_name=COLLECTION_EMBEDDINGS,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True
        )
        
        rag_results = []
        for result in results:
            # Get full message from messages collection
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
        
        return rag_results

    def get_available_sources(self) -> List[RAGSource]:
        # Get unique chat_ids from embeddings collection
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

    def get_stats(self) -> dict:
        try:
            emb_info = self.qdrant.get_collection(COLLECTION_EMBEDDINGS)
            msg_info = self.qdrant.get_collection(COLLECTION_MESSAGES)
            
            return {
                "embeddings_count": emb_info.points_count,
                "messages_count": msg_info.points_count,
                "sources": len(self.get_available_sources())
            }
        except Exception as e:
            return {"error": str(e)}


rag_service = RAGService()
