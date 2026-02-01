import os
import json
import asyncio
from typing import List, Optional, AsyncGenerator
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import (
    Channel, Chat, User, 
    MessageService, Message,
    PeerChannel, PeerChat, PeerUser,
    ChannelForbidden, ChatForbidden,
    ForumTopic as TLForumTopic
)
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.errors import SessionPasswordNeededError
from app.config import get_settings
from app.models import (
    ChatInfo, ChatType, ForumTopic, 
    TelegramMessage, MessageAuthor, DownloadSettings
)


class TelegramService:
    def __init__(self):
        self.settings = get_settings()
        os.makedirs(self.settings.session_dir, exist_ok=True)
        session_path = os.path.join(self.settings.session_dir, "telegram_session")
        
        self.client = TelegramClient(
            session_path,
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash
        )
        self._connected = False
        self._auth_state = "disconnected"
        self._phone_code_hash = None

    async def connect(self):
        if not self._connected:
            await self.client.connect()
            self._connected = True

    async def disconnect(self):
        if self._connected:
            await self.client.disconnect()
            self._connected = False

    async def is_authorized(self) -> bool:
        await self.connect()
        return await self.client.is_user_authorized()

    async def get_auth_status(self) -> dict:
        await self.connect()
        is_auth = await self.client.is_user_authorized()
        
        if is_auth:
            me = await self.client.get_me()
            return {
                "is_authorized": True,
                "phone": self.settings.telegram_phone,
                "user_id": me.id,
                "username": me.username,
                "auth_state": "authorized"
            }
        return {
            "is_authorized": False,
            "phone": self.settings.telegram_phone,
            "auth_state": self._auth_state
        }

    async def send_code(self) -> dict:
        await self.connect()
        try:
            result = await self.client.send_code_request(self.settings.telegram_phone)
            self._phone_code_hash = result.phone_code_hash
            self._auth_state = "code_sent"
            return {"status": "code_sent", "phone": self.settings.telegram_phone}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def sign_in_with_code(self, code: str) -> dict:
        await self.connect()
        try:
            await self.client.sign_in(
                self.settings.telegram_phone, 
                code, 
                phone_code_hash=self._phone_code_hash
            )
            self._auth_state = "authorized"
            me = await self.client.get_me()
            return {
                "status": "authorized",
                "user_id": me.id,
                "username": me.username
            }
        except SessionPasswordNeededError:
            self._auth_state = "2fa_required"
            return {"status": "2fa_required"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def sign_in_with_2fa(self, password: str) -> dict:
        await self.connect()
        try:
            await self.client.sign_in(password=password)
            self._auth_state = "authorized"
            me = await self.client.get_me()
            return {
                "status": "authorized",
                "user_id": me.id,
                "username": me.username
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_chat_type(self, entity) -> ChatType:
        if isinstance(entity, Channel):
            if entity.megagroup:
                if entity.forum:
                    return ChatType.FORUM
                return ChatType.SUPERGROUP
            return ChatType.CHANNEL
        elif isinstance(entity, Chat):
            return ChatType.GROUP
        elif isinstance(entity, User):
            return ChatType.USER
        return ChatType.GROUP

    async def get_dialogs(self) -> List[ChatInfo]:
        await self.connect()
        dialogs = await self.client.get_dialogs()
        
        chats = []
        for dialog in dialogs:
            entity = dialog.entity
            
            if isinstance(entity, (ChannelForbidden, ChatForbidden)):
                continue
                
            chat_type = self._get_chat_type(entity)
            
            title = getattr(entity, 'title', None)
            if not title and isinstance(entity, User):
                title = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                if not title:
                    title = entity.username or f"User {entity.id}"
            
            is_forum = False
            if isinstance(entity, Channel):
                is_forum = getattr(entity, 'forum', False)
            
            chat_info = ChatInfo(
                id=entity.id,
                title=title or "Unknown",
                type=chat_type,
                username=getattr(entity, 'username', None),
                members_count=getattr(entity, 'participants_count', None),
                is_forum=is_forum,
                unread_count=dialog.unread_count
            )
            chats.append(chat_info)
        
        return chats

    async def get_forum_topics(self, chat_id: int) -> List[ForumTopic]:
        await self.connect()
        entity = await self.client.get_entity(chat_id)
        
        if not isinstance(entity, Channel) or not getattr(entity, 'forum', False):
            return []
        
        topics = []
        try:
            result = await self.client(GetForumTopicsRequest(
                channel=entity,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100
            ))
            
            for topic in result.topics:
                if isinstance(topic, TLForumTopic):
                    topics.append(ForumTopic(
                        id=topic.id,
                        title=topic.title,
                        icon_color=topic.icon_color,
                        icon_emoji_id=str(topic.icon_emoji_id) if topic.icon_emoji_id else None
                    ))
        except Exception as e:
            print(f"Error getting forum topics: {e}")
        
        return topics

    async def get_messages(
        self, 
        settings: DownloadSettings
    ) -> AsyncGenerator[TelegramMessage, None]:
        await self.connect()
        entity = await self.client.get_entity(settings.chat_id)
        chat_title = getattr(entity, 'title', str(settings.chat_id))
        
        topic_title = None
        if settings.topic_id:
            topics = await self.get_forum_topics(settings.chat_id)
            for t in topics:
                if t.id == settings.topic_id:
                    topic_title = t.title
                    break
        
        kwargs = {
            'entity': entity,
            'limit': settings.limit,
        }
        
        if settings.offset_id > 0:
            kwargs['offset_id'] = settings.offset_id
        if settings.min_id > 0:
            kwargs['min_id'] = settings.min_id
        if settings.max_id > 0:
            kwargs['max_id'] = settings.max_id
        if settings.topic_id:
            kwargs['reply_to'] = settings.topic_id
        
        async for message in self.client.iter_messages(**kwargs):
            if isinstance(message, MessageService):
                continue
            if not message.text:
                continue
                
            sender = await message.get_sender()
            author = MessageAuthor(
                id=sender.id if sender else 0,
                username=getattr(sender, 'username', None),
                first_name=getattr(sender, 'first_name', None),
                last_name=getattr(sender, 'last_name', None)
            )
            
            yield TelegramMessage(
                id=message.id,
                chat_id=settings.chat_id,
                chat_title=chat_title,
                topic_id=settings.topic_id,
                topic_title=topic_title,
                author=author,
                text=message.text,
                date=message.date,
                reply_to_msg_id=message.reply_to.reply_to_msg_id if message.reply_to else None,
                views=message.views,
                forwards=message.forwards
            )


telegram_service = TelegramService()
