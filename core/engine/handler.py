import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.contracts import IncomingEvent, OutgoingMessage, Platform
from core.engine.llm import generate_text, _history
from core.engine.story_service import get_story_by_id, get_story_snapshot
from infrastructure.db.connection import AsyncSessionFactory
from infrastructure.db.models import (
    User, PlatformAccount, Session, Message, MessageRole, SessionStatus, Story
)

logger = logging.getLogger(__name__)


async def get_or_create_user(db: AsyncSession, platform: Platform, external_id: str) -> User:
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.platform == platform.value,
            PlatformAccount.external_id == external_id,
        )
    )
    account = result.scalar_one_or_none()

    if account:
        result = await db.execute(select(User).where(User.id == account.user_id))
        return result.scalar_one()

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


async def get_active_session(db: AsyncSession, user: User) -> Session | None:
    result = await db.execute(
        select(Session).where(
            Session.user_id == user.id,
            Session.status == SessionStatus.ACTIVE,
        ).order_by(Session.created_at.desc())
    )
    return result.scalar_one_or_none()


async def start_session(db: AsyncSession, user: User, story: Story) -> tuple[Session, str]:
    """Начать новую сессию с историей. Возвращает сессию и вступительное сообщение."""
    # Завершаем предыдущую активную сессию если есть
    old_session = await get_active_session(db, user)
    if old_session:
        old_session.status = SessionStatus.ENDED
        await db.flush()

    session = Session(user_id=user.id, story_id=story.id)
    db.add(session)
    await db.flush()

    # Берём первое вступительное сообщение
    first_message = story.first_messages[0] if story.first_messages else "История начинается..."

    # Сохраняем вступительное сообщение как сообщение ассистента
    db.add(Message(
        session_id=session.id,
        role=MessageRole.ASSISTANT,
        content=first_message,
    ))

    # Инициализируем историю в памяти
    _history[str(session.id)] = [{"role": "assistant", "content": first_message}]

    await db.commit()
    return session, first_message


async def build_system_prompt(db: AsyncSession, story: Story) -> str:
    """Собрать системный промпт из сюжета и персонажа."""
    base = f"Сюжет: {story.plot_ai}\n\n"

    snapshot = await get_story_snapshot(db, str(story.id))
    if snapshot:
        data = snapshot.snapshot_data
        base += f"Ты играешь персонажа {data['name']}.\n"
        base += f"Описание персонажа: {data['description_ai']}\n\n"
        if data.get("example_dialogues"):
            base += f"Примеры диалогов:\n{data['example_dialogues']}\n\n"

    if story.ai_reminder:
        base += f"Важно: {story.ai_reminder}"

    return base


async def load_history_from_db(db: AsyncSession, session: Session) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [{"role": msg.role.value, "content": msg.content} for msg in messages]


async def save_messages(db: AsyncSession, session: Session, user_text: str, assistant_text: str):
    db.add(Message(session_id=session.id, role=MessageRole.USER, content=user_text))
    db.add(Message(session_id=session.id, role=MessageRole.ASSISTANT, content=assistant_text))


async def handle_event(event: IncomingEvent) -> OutgoingMessage:
    async with AsyncSessionFactory() as db:
        try:
            user = await get_or_create_user(db, event.platform, event.external_user_id)
            session = await get_active_session(db, user)

            if not session:
                return OutgoingMessage(
                    external_session_id=event.external_session_id,
                    platform=event.platform,
                    text="Выбери историю командой /play чтобы начать игру.",
                )

            session_key = str(session.id)

            # Загружаем историю из БД если в памяти её нет (после рестарта)
            if session_key not in _history:
                _history[session_key] = await load_history_from_db(db, session)

            # Строим системный промпт с учётом истории
            story = await get_story_by_id(db, str(session.story_id))
            system_prompt = await build_system_prompt(db, story) if story else None

            response_text = await generate_text(
                session_id=session_key,
                user_message=event.text,
                system_prompt=system_prompt,
            )

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