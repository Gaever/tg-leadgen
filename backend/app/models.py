from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ChatType(str, Enum):
    CHANNEL = "channel"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    FORUM = "forum"
    USER = "user"


class ChatInfo(BaseModel):
    id: int
    title: str
    type: ChatType
    username: Optional[str] = None
    members_count: Optional[int] = None
    is_forum: bool = False
    photo_url: Optional[str] = None
    unread_count: int = 0


class ForumTopic(BaseModel):
    id: int
    title: str
    icon_color: Optional[int] = None
    icon_emoji_id: Optional[str] = None
    messages_count: Optional[int] = None


class MessageAuthor(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramMessage(BaseModel):
    id: int
    chat_id: int
    chat_title: str
    chat_username: Optional[str] = None  # для формирования ссылки
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    author: MessageAuthor
    text: str
    date: datetime
    reply_to_msg_id: Optional[int] = None
    views: Optional[int] = None
    forwards: Optional[int] = None
    
    @property
    def telegram_link(self) -> str:
        """Ссылка на сообщение в Telegram"""
        if self.chat_username:
            return f"https://t.me/{self.chat_username}/{self.id}"
        # Для приватных чатов используем формат c/
        # chat_id нужно преобразовать (убрать -100 префикс)
        clean_id = str(self.chat_id)
        if clean_id.startswith("-100"):
            clean_id = clean_id[4:]
        return f"https://t.me/c/{clean_id}/{self.id}"


class ContactInfo(BaseModel):
    """Информация о контакте/пользователе"""
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    birthday: Optional[str] = None  # формат "DD.MM.YYYY" или "DD.MM"
    photo_id: Optional[str] = None
    
    # Связанные данные
    common_chats_count: Optional[int] = None
    personal_channel_id: Optional[int] = None
    personal_channel_title: Optional[str] = None
    
    # Метаданные
    first_seen_chat_id: Optional[int] = None
    first_seen_message_id: Optional[int] = None
    updated_at: Optional[datetime] = None
    messages_count: int = 0
    
    @property
    def telegram_link(self) -> str:
        if self.username:
            return f"https://t.me/{self.username}"
        return f"tg://user?id={self.id}"
    
    @property
    def full_name(self) -> str:
        parts = [self.first_name or "", self.last_name or ""]
        return " ".join(p for p in parts if p).strip() or f"User {self.id}"


class DownloadSettings(BaseModel):
    chat_id: int
    topic_id: Optional[int] = None
    limit: int = 100
    offset_id: int = 0
    min_id: int = 0
    max_id: int = 0


class DownloadStatus(BaseModel):
    chat_id: int
    topic_id: Optional[int] = None
    total_downloaded: int
    status: str
    error: Optional[str] = None


class RAGSource(BaseModel):
    chat_id: int
    chat_title: str
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    messages_count: int


class RAGQuery(BaseModel):
    query: str
    sources: List[int]  # chat_ids
    top_k: int = 10


class RAGResult(BaseModel):
    message: TelegramMessage
    score: float
    highlight: Optional[str] = None


class RAGResponse(BaseModel):
    query: str
    results: List[RAGResult]
    total_found: int


class AuthStatus(BaseModel):
    is_authorized: bool
    phone: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None


class AuthCodeRequest(BaseModel):
    code: str


class Auth2FARequest(BaseModel):
    password: str
