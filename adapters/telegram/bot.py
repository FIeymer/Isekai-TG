import asyncio
import logging
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile, BotCommand
from aiogram.filters import CommandStart, Command

from config.settings import settings
from core.contracts import IncomingEvent, Platform
from core.engine.handler import (
    handle_event, get_or_create_user, get_active_session, start_session
)
from core.engine.story_service import (
    get_public_stories, get_user_stories, create_demo_story,
    get_story_by_id, publish_story, delete_story
)
from infrastructure.db.connection import AsyncSessionFactory
from infrastructure.storage.client import ensure_bucket_exists

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()

LLM_TIMEOUT_SECONDS = 30
IMAGE_POLL_INTERVAL = 2
IMAGE_POLL_TIMEOUT = 60


# FSM состояния для создания истории
class CreateStory(StatesGroup):
    title = State()
    plot_summary = State()
    plot_ai = State()
    character_name = State()
    character_description = State()
    first_message = State()


@dp.startup()
async def on_startup():
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="play", description="Каталог публичных историй"),
        BotCommand(command="mystories", description="Мои истории"),
        BotCommand(command="create", description="Создать свою историю"),
        BotCommand(command="new", description="Создать демо-историю"),
        BotCommand(command="stop", description="Завершить текущую игру"),
        BotCommand(command="cancel", description="Отменить создание истории"),
    ])
    try:
        ensure_bucket_exists()
        logger.info("Storage bucket ready")
    except Exception as e:
        logger.warning(f"Storage init failed (non-critical): {e}")


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Добро пожаловать в Storyweave! 🎮\n\n"
        "Команды:\n"
        "/play — каталог публичных историй\n"
        "/mystories — мои истории\n"
        "/create — создать свою историю\n"
        "/new — создать демо-историю\n"
        "/stop — завершить текущую игру"
    )


# ─── Создание истории (FSM) ───────────────────────────────────────────────────

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("❌ Создание истории отменено.")


@dp.message(Command("create"))
async def cmd_create(message: Message, state: FSMContext):
    await state.set_state(CreateStory.title)
    await message.answer(
        "📝 *Создание истории* (шаг 1/6)\n\n"
        "Введи *название* истории:\n\n"
        "_/cancel — отменить_",
        parse_mode="Markdown",
    )


@dp.message(CreateStory.title)
async def create_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(CreateStory.plot_summary)
    await message.answer(
        "📝 *Создание истории* (шаг 2/6)\n\n"
        "Введи *краткое описание* для игрока (1-2 предложения — анонс истории):\n\n"
        "_/cancel — отменить_",
        parse_mode="Markdown",
    )


@dp.message(CreateStory.plot_summary)
async def create_plot_summary(message: Message, state: FSMContext):
    await state.update_data(plot_summary=message.text)
    await state.set_state(CreateStory.plot_ai)
    await message.answer(
        "📝 *Создание истории* (шаг 3/6)\n\n"
        "Введи *полный сюжет для ИИ* — подробное описание мира, тайн, направление истории:\n\n"
        "_/cancel — отменить_",
        parse_mode="Markdown",
    )


@dp.message(CreateStory.plot_ai)
async def create_plot_ai(message: Message, state: FSMContext):
    await state.update_data(plot_ai=message.text)
    await state.set_state(CreateStory.character_name)
    await message.answer(
        "📝 *Создание истории* (шаг 4/6)\n\n"
        "Введи *имя главного персонажа* которого будет играть ИИ:\n\n"
        "_/cancel — отменить_",
        parse_mode="Markdown",
    )


@dp.message(CreateStory.character_name)
async def create_character_name(message: Message, state: FSMContext):
    await state.update_data(character_name=message.text)
    await state.set_state(CreateStory.character_description)
    await message.answer(
        "📝 *Создание истории* (шаг 5/6)\n\n"
        "Введи *описание персонажа для ИИ* — характер, манера речи, тайны, мотивация:\n\n"
        "_/cancel — отменить_",
        parse_mode="Markdown",
    )


@dp.message(CreateStory.character_description)
async def create_character_description(message: Message, state: FSMContext):
    await state.update_data(character_description=message.text)
    await state.set_state(CreateStory.first_message)
    await message.answer(
        "📝 *Создание истории* (шаг 6/6)\n\n"
        "Введи *вступительное сообщение* — первое что увидит игрок когда начнёт историю:\n\n"
        "_/cancel — отменить_",
        parse_mode="Markdown",
    )


@dp.message(CreateStory.first_message)
async def create_first_message(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    async with AsyncSessionFactory() as db:
        from infrastructure.db.models import Story, Character, StoryCharacterSnapshot, Visibility
        user = await get_or_create_user(db, Platform.TELEGRAM, str(message.from_user.id))

        character = Character(
            author_id=user.id,
            name=data["character_name"],
            description_player="",
            description_ai=data["character_description"],
            visibility=Visibility.PRIVATE,
        )
        db.add(character)
        await db.flush()

        story = Story(
            author_id=user.id,
            title=data["title"],
            plot_summary_player=data["plot_summary"],
            plot_ai=data["plot_ai"],
            ai_reminder=(
                f'Ты играешь {data["character_name"]}. '
                'Веди историю в образе, предлагай 2-3 варианта действий в конце каждого хода.'
            ),
            first_messages=[message.text],
            visibility=Visibility.PRIVATE,
        )
        db.add(story)
        await db.flush()

        snapshot = StoryCharacterSnapshot(
            story_id=story.id,
            character_id=character.id,
            snapshot_data={
                "name": character.name,
                "description_ai": character.description_ai,
                "example_dialogues": "",
            }
        )
        db.add(snapshot)
        await db.commit()

    await message.answer(
        f"✅ История *{data['title']}* создана!\n\n"
        "Она сохранена как личная. Открой /mystories чтобы сыграть или опубликовать.",
        parse_mode="Markdown",
    )


# ─── Остальные команды ────────────────────────────────────────────────────────

@dp.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(message.from_user.id))
        story, created = await create_demo_story(db, user)

    if created:
        await message.answer(
            f"✅ Создана демо-история: *{story.title}*\n\n"
            f"{story.plot_summary_player}\n\n"
            "История сохранена как личная. Открой /mystories чтобы управлять ей.",
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            f"Демо-история *{story.title}* уже существует.\n\n"
            "Открой /mystories чтобы управлять ей.",
            parse_mode="Markdown",
        )


@dp.message(Command("mystories"))
async def cmd_mystories(message: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(message.from_user.id))
        stories = await get_user_stories(db, user)

    if not stories:
        await message.answer(
            "У тебя нет историй.\n"
            "/create — создать свою\n"
            "/new — создать демо-историю"
        )
        return

    for story in stories:
        status = "📢 Публичная" if story.visibility == "PUBLIC" else "🔒 Личная"
        buttons = [
            [InlineKeyboardButton(text="▶️ Играть", callback_data=f"play:{story.id}")],
        ]
        if story.visibility != "PUBLIC":
            buttons.append([
                InlineKeyboardButton(text="📢 Опубликовать", callback_data=f"publish:{story.id}")
            ])
        buttons.append([
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete:{story.id}")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(
            f"*{story.title}*\n{status}\n\n{story.plot_summary_player}",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


@dp.message(Command("play"))
async def cmd_play(message: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionFactory() as db:
        stories = await get_public_stories(db)

    if not stories:
        await message.answer(
            "Нет публичных историй.\n"
            "Создай свою через /create и опубликуй через /mystories"
        )
        return

    buttons = [
        [InlineKeyboardButton(text=f"📖 {s.title}", callback_data=f"play:{s.id}")]
        for s in stories
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери историю:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith("play:"))
async def on_story_selected(callback: CallbackQuery):
    story_id = callback.data.split(":", 1)[1]

    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(callback.from_user.id))
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


@dp.callback_query(lambda c: c.data.startswith("publish:"))
async def on_publish(callback: CallbackQuery):
    story_id = callback.data.split(":", 1)[1]

    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(callback.from_user.id))
        success = await publish_story(db, story_id, user)

    if success:
        await callback.answer("✅ История опубликована!", show_alert=True)
        story_buttons = [
            [InlineKeyboardButton(text="▶️ Играть", callback_data=f"play:{story_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete:{story_id}")],
        ]
        try:
            await callback.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(inline_keyboard=story_buttons)
            )
        except Exception:
            pass
    else:
        await callback.answer("Ошибка при публикации.", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("delete:"))
async def on_delete(callback: CallbackQuery):
    story_id = callback.data.split(":", 1)[1]

    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(callback.from_user.id))
        success = await delete_story(db, story_id, user)

    if success:
        await callback.answer("🗑️ История удалена.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
    else:
        await callback.answer("Ошибка при удалении.", show_alert=True)


@dp.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionFactory() as db:
        user = await get_or_create_user(db, Platform.TELEGRAM, str(message.from_user.id))
        session = await get_active_session(db, user)

        if not session:
            await message.answer("Нет активной игры.")
            return

        from infrastructure.db.models import SessionStatus
        session.status = SessionStatus.ENDED
        await db.commit()

    await message.answer("Игра завершена. Напиши /play или /mystories чтобы начать новую.")


async def wait_and_send_image(chat_id: int, job_id: str, status_msg_id: int):
    from sqlalchemy import select
    from infrastructure.db.models import GenerationJob, JobStatus

    elapsed = 0
    while elapsed < IMAGE_POLL_TIMEOUT:
        await asyncio.sleep(IMAGE_POLL_INTERVAL)
        elapsed += IMAGE_POLL_INTERVAL

        async with AsyncSessionFactory() as db:
            result = await db.execute(
                select(GenerationJob).where(GenerationJob.id == job_id)
            )
            job = result.scalar_one_or_none()

        if not job:
            await bot.delete_message(chat_id, status_msg_id)
            return

        if job.status == JobStatus.DONE and job.result_url:
            await bot.delete_message(chat_id, status_msg_id)
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(job.result_url, timeout=30)
                    resp.raise_for_status()
                await bot.send_photo(
                    chat_id,
                    BufferedInputFile(resp.content, filename="scene.png")
                )
            except Exception as e:
                logger.error(f"Failed to send image: {e}")
            return

        if job.status == JobStatus.FAILED:
            await bot.edit_message_text(
                "⚠️ Не удалось сгенерировать изображение.",
                chat_id=chat_id,
                message_id=status_msg_id,
            )
            return

    await bot.edit_message_text(
        "⏱️ Генерация изображения заняла слишком долго.",
        chat_id=chat_id,
        message_id=status_msg_id,
    )


@dp.message()
async def on_message(message: Message, state: FSMContext):
    # Если активен FSM — не обрабатываем как игровое сообщение
    current_state = await state.get_state()
    if current_state is not None:
        return

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

    async def typing_loop():
        while True:
            await bot.send_chat_action(message.chat.id, "typing")
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(typing_loop())

    try:
        response = await asyncio.wait_for(
            handle_event(event),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        await message.answer(response.text)

        if response.image_job_id:
            status_msg = await message.answer("🎨 Генерирую изображение...")
            asyncio.create_task(
                wait_and_send_image(message.chat.id, response.image_job_id, status_msg.message_id)
            )

    except asyncio.TimeoutError:
        logger.error(f"LLM timeout for user {message.from_user.id}")
        await message.answer("⏱️ Ответ занял слишком долго. Попробуй ещё раз.")
    except Exception as e:
        logger.error(f"Unexpected error for user {message.from_user.id}: {e}")
        await message.answer("⚠️ Что-то пошло не так. Попробуй ещё раз.")
    finally:
        typing_task.cancel()


async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())