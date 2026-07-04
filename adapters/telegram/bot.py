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


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Добро пожаловать в Storyweave! 🎮\n\n"
        "Напиши что-нибудь чтобы начать игру."
    )


@dp.message()
async def on_message(message: Message):
    if not message.text:
        return

    event = IncomingEvent(
        platform=Platform.TELEGRAM,
        external_user_id=str(message.from_user.id),
        external_session_id=str(message.chat.id),
        text=message.text,
    )

    response = await handle_event(event)
    await message.answer(response.text)


async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())