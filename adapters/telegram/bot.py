import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart

from config.settings import settings
from core.contracts import IncomingEvent, Platform
from core.engine.handler import handle_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()

LLM_TIMEOUT_SECONDS = 30


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Добро пожаловать в Storyweave! 🎮\n\n"
        "Напиши что-нибудь чтобы начать игру."
    )


@dp.message()
async def on_message(message: Message):
    # Игнорируем нетекстовые сообщения
    if not message.text:
        await message.answer("✍️ Отправь текстовое сообщение.")
        return

    # Лимит длины сообщения
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