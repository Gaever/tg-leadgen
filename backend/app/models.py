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
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    author: MessageAuthor
    text: str
    date: datetime
    reply_to_msg_id: Optional[int] = None
    views: Optional[int] = None
    forwards: Optional[int] = None


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
