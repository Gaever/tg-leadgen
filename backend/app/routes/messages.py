from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List
import json
import asyncio
from app.telegram_client import telegram_service
from app.rag_service import rag_service
from app.models import DownloadSettings, DownloadStatus, TelegramMessage

router = APIRouter(prefix="/api/messages", tags=["messages"])


async def enrich_contacts_background(author_ids: List[int]):
    """Фоновое обогащение контактов с rate limiting"""
    new_ids = rag_service.get_new_contact_ids(author_ids)
    
    for user_id in new_ids[:50]:  # Лимит за один раз
        try:
            contact = await telegram_service.get_user_full_info(user_id)
            if contact:
                rag_service.add_contact(contact)
            await asyncio.sleep(1)  # Rate limit: 1 запрос в секунду
        except Exception as e:
            print(f"Error enriching contact {user_id}: {e}")
            if "flood" in str(e).lower():
                break  # Остановить при flood wait


@router.post("/download")
async def download_messages(settings: DownloadSettings, background_tasks: BackgroundTasks):
    """Скачать сообщения из чата и проиндексировать в RAG"""
    if not await telegram_service.is_authorized():
        raise HTTPException(status_code=401, detail="Not authorized in Telegram")
    
    async def generate():
        messages_batch = []
        author_ids = []
        total_downloaded = 0
        
        try:
            async for message in telegram_service.get_messages(settings):
                messages_batch.append(message)
                author_ids.append(message.author.id)
                total_downloaded += 1
                
                yield json.dumps({
                    "type": "progress",
                    "downloaded": total_downloaded,
                    "message_preview": message.text[:100] + "..." if len(message.text) > 100 else message.text
                }) + "\n"
                
                if len(messages_batch) >= 50:
                    indexed = await rag_service.index_messages_batch(messages_batch)
                    yield json.dumps({
                        "type": "indexed",
                        "count": indexed
                    }) + "\n"
                    messages_batch = []
                
                await asyncio.sleep(0.05)
            
            if messages_batch:
                indexed = await rag_service.index_messages_batch(messages_batch)
                yield json.dumps({
                    "type": "indexed",
                    "count": indexed
                }) + "\n"
            
            # Запускаем обогащение контактов в фоне
            new_contacts = len(rag_service.get_new_contact_ids(author_ids))
            if new_contacts > 0:
                background_tasks.add_task(enrich_contacts_background, author_ids)
                yield json.dumps({
                    "type": "contacts_queued",
                    "count": min(new_contacts, 50)
                }) + "\n"
            
            yield json.dumps({
                "type": "complete",
                "total_downloaded": total_downloaded,
                "status": "success"
            }) + "\n"
            
        except Exception as e:
            yield json.dumps({
                "type": "error",
                "error": str(e)
            }) + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )


@router.get("/stats")
async def get_stats():
    """Получить статистику по скачанным сообщениям"""
    return rag_service.get_stats()
