from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
from app.rag_service import rag_service
from app.models import (
    RAGQuery,
    RAGResponse,
    RAGSource,
    RAGResult,
    ContactInfo,
    RAGAnswerRequest,
    RAGAnswerResponse,
    RAGAnswerFilters
)

router = APIRouter(prefix="/api/rag", tags=["rag"])


class ContactSearchQuery(BaseModel):
    query: str
    top_k: int = 20


class ContactSearchResult(BaseModel):
    contact: ContactInfo
    score: float
    messages_count: int = 0


@router.get("/sources", response_model=List[RAGSource])
async def get_sources():
    """Получить список доступных источников (скачанных чатов)"""
    return rag_service.get_available_sources()


@router.get("/sources/export")
async def export_sources():
    """Экспорт источников в JSON"""
    sources = rag_service.get_available_sources()
    return JSONResponse(
        content=[s.model_dump() for s in sources],
        headers={
            "Content-Disposition": "attachment; filename=sources.json"
        }
    )


@router.get("/messages/export")
async def export_messages():
    """Экспорт всех сообщений в JSON"""
    messages = rag_service.get_all_messages()
    return JSONResponse(
        content=messages,
        headers={
            "Content-Disposition": "attachment; filename=messages.json"
        }
    )


@router.post("/search", response_model=RAGResponse)
async def search_messages(
    query: RAGQuery,
    min_text_length: int = Query(default=50, description="Минимальная длина текста сообщения"),
    expand_query: bool = Query(default=True, description="Расширять запрос через LLM")
):
    """Поиск сообщений по запросу с фильтрацией по источникам"""
    results = await rag_service.search(
        query=query.query,
        chat_ids=query.sources,
        top_k=query.top_k,
        min_text_length=min_text_length,
        expand_query=expand_query
    )
    
    return RAGResponse(
        query=query.query,
        results=results,
        total_found=len(results)
    )


@router.post("/answer", response_model=RAGAnswerResponse)
async def get_rag_answer(request: RAGAnswerRequest):
    """Синтезированный ответ на запрос пользователя"""
    filters = request.filters or RAGAnswerFilters()
    chat_ids = filters.chatIds
    if not chat_ids:
        chat_ids = [source.chat_id for source in rag_service.get_available_sources()]

    response = await rag_service.generate_answer(
        query=request.query,
        chat_ids=chat_ids,
        top_k=request.topK,
        answer_style=request.answerStyle,
        date_from=filters.dateFrom,
        date_to=filters.dateTo,
        min_score=filters.minScore
    )
    return response


@router.get("/contacts", response_model=List[ContactInfo])
async def get_contacts():
    """Получить все контакты"""
    return rag_service.get_all_contacts()


@router.get("/contacts/export")
async def export_contacts():
    """Экспорт контактов в JSON"""
    contacts = rag_service.get_all_contacts()
    return JSONResponse(
        content=[c.model_dump() for c in contacts],
        headers={
            "Content-Disposition": "attachment; filename=contacts.json"
        }
    )


@router.post("/contacts/search")
async def search_contacts(
    query: ContactSearchQuery,
    expand_query: bool = Query(default=True, description="Расширять запрос через LLM")
):
    """Поиск контактов по bio"""
    results = await rag_service.search_contacts(
        query=query.query,
        top_k=query.top_k,
        expand_query=expand_query
    )
    
    # Добавляем количество сообщений
    enriched_results = []
    for r in results:
        enriched_results.append({
            "contact": r["contact"].model_dump(),
            "score": r["score"],
            "messages_count": rag_service.get_contact_messages_count(r["contact"].id)
        })
    
    return {
        "query": query.query,
        "results": enriched_results,
        "total_found": len(enriched_results)
    }


@router.get("/contacts/{user_id}")
async def get_contact(user_id: int):
    """Получить контакт по ID с количеством сообщений"""
    contact = rag_service.get_contact(user_id)
    if not contact:
        return {"error": "Contact not found"}
    
    return {
        "contact": contact.model_dump(),
        "messages_count": rag_service.get_contact_messages_count(user_id)
    }


@router.get("/stats")
async def get_rag_stats():
    """Получить статистику RAG"""
    return rag_service.get_stats()


@router.delete("/sources/{chat_id}")
async def delete_source(chat_id: int, topic_id: Optional[int] = Query(default=None)):
    """Удалить источник из базы"""
    result = rag_service.delete_source(chat_id, topic_id)
    return result
