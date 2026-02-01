from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List
import json
import asyncio
from app.telegram_client import telegram_service
from app.rag_service import rag_service
from app.models import DownloadSettings, DownloadStatus, TelegramMessage

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.post("/download")
async def download_messages(settings: DownloadSettings):
    """Скачать сообщения из чата и проиндексировать в RAG"""
    if not await telegram_service.is_authorized():
        raise HTTPException(status_code=401, detail="Not authorized in Telegram")
    
    async def generate():
        messages_batch = []
        total_downloaded = 0
        
        try:
            async for message in telegram_service.get_messages(settings):
                messages_batch.append(message)
                total_downloaded += 1
                
                # Send progress update
                yield json.dumps({
                    "type": "progress",
                    "downloaded": total_downloaded,
                    "message_preview": message.text[:100] + "..." if len(message.text) > 100 else message.text
                }) + "\n"
                
                # Index in batches of 50
                if len(messages_batch) >= 50:
                    indexed = await rag_service.index_messages_batch(messages_batch)
                    yield json.dumps({
                        "type": "indexed",
                        "count": indexed
                    }) + "\n"
                    messages_batch = []
                
                # Small delay to not overwhelm Telegram API
                await asyncio.sleep(0.05)
            
            # Index remaining messages
            if messages_batch:
                indexed = await rag_service.index_messages_batch(messages_batch)
                yield json.dumps({
                    "type": "indexed",
                    "count": indexed
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
