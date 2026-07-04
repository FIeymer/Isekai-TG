"""
Модели базы данных.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, ForeignKey,
    Enum, JSON, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Platform(str, PyEnum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WEB = "web"


class Visibility(str, PyEnum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class SessionStatus(str, PyEnum):
    ACTIVE = "active"
    ENDED = "ended"


class MessageRole(str, PyEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class JobType(str, PyEnum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"


class JobStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class User(Base):
    """Пользователь — не привязан к конкретной платформе."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, server_default=func.now())

    platform_accounts = relationship("PlatformAccount", back_populates="user")
    characters = relationship("Character", back_populates="author")
    stories = relationship("Story", back_populates="author")
    sessions = relationship("Session", back_populates="user")


class PlatformAccount(Base):
    """Привязка пользователя к конкретной платформе."""
    __tablename__ = "platform_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform = Column(Enum(Platform), nullable=False)
    external_id = Column(String(255), nullable=False)  # telegram chat_id живёт здесь
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="platform_accounts")


class Character(Base):
    """Персонаж, созданный пользователем."""
    __tablename__ = "characters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String(255), nullable=False)
    # Для игрока — краткий тизер, не отправляется ИИ
    description_player = Column(Text, nullable=False, default="")
    # Для ИИ — полные инструкции
    description_ai = Column(Text, nullable=False, default="")
    example_dialogues = Column(Text, nullable=True)

    visibility = Column(Enum(Visibility), default=Visibility.PRIVATE)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    author = relationship("User", back_populates="characters")


class Story(Base):
    """История, созданная пользователем."""
    __tablename__ = "stories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    # Для игрока — краткий анонс, не отправляется ИИ
    plot_summary_player = Column(String(500), nullable=False, default="")
    # Для ИИ — полный сюжет
    plot_ai = Column(Text, nullable=False, default="")
    # Напоминание, вводимое повторно каждый ход
    ai_reminder = Column(Text, nullable=True)
    # Одна или несколько вступительных сцен
    first_messages = Column(JSON, default=list)  # list[str]

    visibility = Column(Enum(Visibility), default=Visibility.PRIVATE)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    author = relationship("User", back_populates="stories")
    character_snapshots = relationship("StoryCharacterSnapshot", back_populates="story")
    sessions = relationship("Session", back_populates="story")


class StoryCharacterSnapshot(Base):
    """
    Снапшот персонажа на момент публикации истории.
    Редактирование персонажа после публикации не меняет живые истории.
    """
    __tablename__ = "story_character_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id = Column(UUID(as_uuid=True), ForeignKey("stories.id"), nullable=False)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False)
    # Копия данных персонажа на момент публикации, не ссылка
    snapshot_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    story = relationship("Story", back_populates="character_snapshots")


class Session(Base):
    """Игровая сессия — один пользователь играет в одну историю."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    story_id = Column(UUID(as_uuid=True), ForeignKey("stories.id"), nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="sessions")
    story = relationship("Story", back_populates="sessions")
    messages = relationship("Message", back_populates="session", order_by="Message.created_at")
    jobs = relationship("GenerationJob", back_populates="session")


class Message(Base):
    """Одно сообщение в игровой сессии."""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    session = relationship("Session", back_populates="messages")


class GenerationJob(Base):
    """Задача генерации (изображение, голос и т.д.) в очереди."""
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    type = Column(Enum(JobType), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    prompt = Column(Text, nullable=False)
    result_url = Column(String(1024), nullable=True)
    error = Column(Text, nullable=True)
    provider_used = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    session = relationship("Session", back_populates="jobs")
