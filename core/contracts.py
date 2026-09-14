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
    platform: Platform
    external_user_id: str
    external_session_id: str
    text: str
    user_id: Optional[UUID] = None
    session_id: Optional[UUID] = None


@dataclass
class MediaAttachment:
    type: MediaType
    url: str


@dataclass
class OutgoingMessage:
    external_session_id: str
    platform: Platform
    text: str
    media: list[MediaAttachment] = field(default_factory=list)
    choices: list[str] = field(default_factory=list)
    image_job_id: Optional[str] = None


@dataclass
class GenerationRequest:
    job_id: UUID
    session_id: UUID
    type: MediaType
    prompt: str
    style_hint: Optional[str] = None
