import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.contracts import IncomingEvent, OutgoingMessage, Platform
from core.engine.llm import generate_text, _history
from infrastructure.db.connection import AsyncSessionFactory
from infrastructure.db.models import (
    User, PlatformAccount, Session, Message, MessageRole, SessionStatus
)

logger = logging.getLogger(__name__)


async def get_or_create_user(db: AsyncSession, platform: Platform, external_id: str) -> User:
    """Найти или создать пользователя по platform + external_id."""
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.platform == platform.value,
            PlatformAccount.external_id == external_id,
        )
    )
    account = result.scalar_one_or_none()

    if account:
        return account.user

    user = User()
    db.add(user)
    await db.flush()

    account = PlatformAccount(
        user_id=user.id,
        platform=platform.value,
        external_id=external_id,
    )
    db.add(account)
    await db.flush()

    return user


async def get_or_create_session(db: AsyncSession, user: User) -> Session:
    """Найти активную сессию или создать новую."""
    result = await db.execute(
        select(Session).where(
            Session.user_id == user.id,
            Session.status == SessionStatus.ACTIVE,
        ).order_by(Session.created_at.desc())
    )
    session = result.scalar_one_or_none()

    if session:
        return session

    session = Session(user_id=user.id, story_id=None)
    db.add(session)
    await db.flush()

    return session


async def load_history_from_db(db: AsyncSession, session: Session) -> list[dict]:
    """Загрузить историю сообщений из БД."""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [{"role": msg.role.value, "content": msg.content} for msg in messages]


async def save_messages(db: AsyncSession, session: Session, user_text: str, assistant_text: str):
    """Сохранить пару сообщений в БД."""
    db.add(Message(session_id=session.id, role=MessageRole.USER, content=user_text))
    db.add(Message(session_id=session.id, role=MessageRole.ASSISTANT, content=assistant_text))


async def handle_event(event: IncomingEvent) -> OutgoingMessage:
    async with AsyncSessionFactory() as db:
        try:
            user = await get_or_create_user(db, event.platform, event.external_user_id)
            session = await get_or_create_session(db, user)

            session_key = str(session.id)

            # Загружаем историю из БД если в памяти её нет (после рестарта)
            if session_key not in _history:
                _history[session_key] = await load_history_from_db(db, session)

            response_text = await generate_text(
                session_id=session_key,
                user_message=event.text,
            )

            # Сохраняем только если ответ не техническое сообщение
            if not response_text.startswith(("⏳", "⚠️")):
                await save_messages(db, session, event.text, response_text)
                await db.commit()

        except Exception as e:
            logger.error(f"Handler error: {e}")
            await db.rollback()
            response_text = "⚠️ Внутренняя ошибка. Попробуй ещё раз."

    return OutgoingMessage(
        external_session_id=event.external_session_id,
        platform=event.platform,
        text=response_text,
    )