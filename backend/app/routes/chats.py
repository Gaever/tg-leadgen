from fastapi import APIRouter, HTTPException
from typing import List
from app.telegram_client import telegram_service
from app.models import (
    ChatInfo, ForumTopic, AuthStatus,
    AuthCodeRequest, Auth2FARequest
)

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("/auth/status", response_model=dict)
async def get_auth_status():
    """Получить статус авторизации Telegram"""
    return await telegram_service.get_auth_status()


@router.post("/auth/send-code")
async def send_auth_code():
    """Отправить код авторизации на телефон"""
    return await telegram_service.send_code()


@router.post("/auth/verify-code")
async def verify_auth_code(request: AuthCodeRequest):
    """Подтвердить код авторизации"""
    return await telegram_service.sign_in_with_code(request.code)


@router.post("/auth/verify-2fa")
async def verify_2fa(request: Auth2FARequest):
    """Подтвердить двухфакторную аутентификацию"""
    return await telegram_service.sign_in_with_2fa(request.password)


@router.get("/", response_model=List[ChatInfo])
async def get_chats():
    """Получить список всех диалогов"""
    if not await telegram_service.is_authorized():
        raise HTTPException(status_code=401, detail="Not authorized in Telegram")
    
    return await telegram_service.get_dialogs()


@router.get("/{chat_id}/topics", response_model=List[ForumTopic])
async def get_chat_topics(chat_id: int):
    """Получить топики форума (если чат - форум)"""
    if not await telegram_service.is_authorized():
        raise HTTPException(status_code=401, detail="Not authorized in Telegram")
    
    return await telegram_service.get_forum_topics(chat_id)
