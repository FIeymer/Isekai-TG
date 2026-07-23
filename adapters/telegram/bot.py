import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command

from config.settings import settings
from core.contracts import IncomingEvent, Platform
from core.engine.handler import (
    handle_event, get_or_create_user, get_active_session, start_session
)
from core.engine.story_service import get_public_stories, create_demo_story
from infrastructure.db.connection import AsyncSessionFactory
from infrastructure.db.models import Platform as PlatformModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()

LLM_TIMEOUT_SECONDS = 30


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Добро пожаловать в Storyweave! 🎮\n\n"
        "Команды:\n"
        "/play — выбрать историю\n"
        "/new — создать демо-историю\n"
        "/stop — завершить текущую игру"
    )


@dp.message(Command("new"))
async def cmd_new(message: Message):
    """Создать демо-историю."""
    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(message.from_user.id))
        story = await create_demo_story(db, user)
    await message.answer(
        f"✅ Создана история: *{story.title}*\n\n"
        f"{story.plot_summary_player}\n\n"
        "Напиши /play чтобы начать игру.",
        parse_mode="Markdown",
    )


@dp.message(Command("play"))
async def cmd_play(message: Message):
    """Показать список историй."""
    async with AsyncSessionFactory() as db:
        stories = await get_public_stories(db)

    if not stories:
        await message.answer(
            "Нет доступных историй. Создай демо командой /new"
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"📖 {s.title}",
            callback_data=f"play:{s.id}"
        )]
        for s in stories
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери историю:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith("play:"))
async def on_story_selected(callback: CallbackQuery):
    """Начать выбранную историю."""
    story_id = callback.data.split(":", 1)[1]

    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(callback.from_user.id))

        from core.engine.story_service import get_story_by_id
        story = await get_story_by_id(db, story_id)

        if not story:
            await callback.answer("История не найдена.", show_alert=True)
            return

        _, first_message = await start_session(db, user, story)

    await callback.message.answer(
        f"*{story.title}*\n\n{first_message}",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    """Завершить текущую сессию."""
    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(message.from_user.id))
        session = await get_active_session(db, user)

        if not session:
            await message.answer("Нет активной игры.")
            return

        from infrastructure.db.models import SessionStatus
        session.status = SessionStatus.ENDED
        await db.commit()

    await message.answer("Игра завершена. Напиши /play чтобы начать новую.")


@dp.message()
async def on_message(message: Message):
    if not message.text:
        await message.answer("✍️ Отправь текстовое сообщение.")
        return

    if len(message.text) > 1000:
        await message.answer("✂️ Сообщение слишком длинное. Максимум 1000 символов.")
        return

    event = IncomingEvent(
        platform=Platform.TELEGRAM,
        external_user_id=str(message.from_user.id),
        external_session_id=str(message.chat.id),
        text=message.text,
    )

    try:
        response = await asyncio.wait_for(
            handle_event(event),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        await message.answer(response.text)
    except asyncio.TimeoutError:
        logger.error(f"LLM timeout for user {message.from_user.id}")
        await message.answer("⏱️ Ответ занял слишком долго. Попробуй ещё раз.")
    except Exception as e:
        logger.error(f"Unexpected error for user {message.from_user.id}: {e}")
        await message.answer("⚠️ Что-то пошло не так. Попробуй ещё раз.")


async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())