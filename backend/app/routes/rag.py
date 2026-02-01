from fastapi import APIRouter
from typing import List
from app.rag_service import rag_service
from app.models import RAGQuery, RAGResponse, RAGSource, RAGResult

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("/sources", response_model=List[RAGSource])
async def get_sources():
    """Получить список доступных источников (скачанных чатов)"""
    return rag_service.get_available_sources()


@router.post("/search", response_model=RAGResponse)
async def search_messages(query: RAGQuery):
    """Поиск сообщений по запросу с фильтрацией по источникам"""
    results = await rag_service.search(
        query=query.query,
        chat_ids=query.sources,
        top_k=query.top_k
    )
    
    return RAGResponse(
        query=query.query,
        results=results,
        total_found=len(results)
    )


@router.get("/stats")
async def get_rag_stats():
    """Получить статистику RAG"""
    return rag_service.get_stats()
