"""
Нейтральные контракты между ядром и адаптерами интерфейсов.
Никакого кода Telegram, Discord или любого другого интерфейса здесь нет.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import UUID


class Platform(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WEB = "web"


class MediaType(str, Enum):
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"


@dataclass
class IncomingEvent:
    """Нейтральное входящее событие от любого интерфейса."""
    platform: Platform
    external_user_id: str        # telegram user_id, discord user_id, etc.
    external_session_id: str     # telegram chat_id, discord channel_id, etc.
    text: str
    user_id: Optional[UUID] = None      # заполняется ядром после поиска/создания
    session_id: Optional[UUID] = None   # заполняется ядром после поиска/создания


@dataclass
class MediaAttachment:
    type: MediaType
    url: str


@dataclass
class OutgoingMessage:
    """Нейтральное исходящее сообщение в любой интерфейс."""
    external_session_id: str
    platform: Platform
    text: str
    media: list[MediaAttachment] = field(default_factory=list)
    # Варианты быстрых ответов (кнопки / inline-клавиатура)
    choices: list[str] = field(default_factory=list)


@dataclass
class GenerationRequest:
    """Запрос на генерацию медиа — кидается в очередь воркером."""
    job_id: UUID
    session_id: UUID
    type: MediaType
    prompt: str
    style_hint: Optional[str] = None
