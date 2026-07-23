import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import Story, Character, StoryCharacterSnapshot, User

logger = logging.getLogger(__name__)


async def get_public_stories(db: AsyncSession) -> list[Story]:
    """Получить список публичных историй."""
    result = await db.execute(
        select(Story)
        .where(Story.visibility == "public")
        .order_by(Story.created_at.desc())
        .limit(10)
    )
    return result.scalars().all()


async def get_story_by_id(db: AsyncSession, story_id: str) -> Story | None:
    """Получить историю по ID."""
    result = await db.execute(
        select(Story).where(Story.id == story_id)
    )
    return result.scalar_one_or_none()


async def get_story_snapshot(db: AsyncSession, story_id: str) -> StoryCharacterSnapshot | None:
    """Получить снапшот персонажа для истории."""
    result = await db.execute(
        select(StoryCharacterSnapshot)
        .where(StoryCharacterSnapshot.story_id == story_id)
    )
    return result.scalar_one_or_none()


async def create_demo_story(db: AsyncSession, author: User) -> Story:
    """Создать демо-историю для тестирования."""
    # Создаём персонажа
    character = Character(
        author_id=author.id,
        name="Эльяра",
        description_player="Таинственная эльфийская волшебница с тёмным прошлым.",
        description_ai=(
            "Ты — Эльяра, эльфийская волшебница 300 лет от роду. "
            "Ты говоришь загадочно и мудро, иногда цитируешь древние пророчества. "
            "Ты помогаешь герою, но скрываешь свои истинные мотивы. "
            "Никогда не выходи из образа."
        ),
        example_dialogues=(
            "Герой: Кто ты?\n"
            "Эльяра: Я — лишь тень прошлого, странник. Вопрос не в том, кто я, "
            "а в том, готов ли ты узнать правду о себе."
        ),
        visibility="public",
    )
    db.add(character)
    await db.flush()

    # Создаём историю
    story = Story(
        author_id=author.id,
        title="Проклятие Тёмного леса",
        plot_summary_player=(
            "Ты просыпаешься у костра на опушке зловещего леса. "
            "Рядом — запечатанное письмо с твоим именем..."
        ),
        plot_ai=(
            "Действие происходит в тёмном фэнтезийном мире. "
            "Герой — искатель приключений без памяти о прошлом. "
            "Главная тайна: герой является последним хранителем древней магии, "
            "которая может уничтожить или спасти мир. "
            "Эльяра знает правду, но открывает её постепенно. "
            "Веди историю в сторону раскрытия тайны прошлого героя. "
            "Создавай напряжение, опасность и моменты выбора."
        ),
        ai_reminder=(
            "Ты играешь Эльяру. Веди историю в образе, "
            "предлагай 2-3 варианта действий в конце каждого хода."
        ),
        first_messages=[
            "Ты приходишь в себя у догорающего костра. Тёмный лес окружает тебя со всех сторон — "
            "где-то вдалеке слышен вой, а рядом лежит запечатанное письмо с твоим именем.\n\n"
            "Из теней выступает фигура в тёмном плаще.\n\n"
            "— Наконец-то ты проснулся, — говорит незнакомка. — Времени мало. Они уже идут.\n\n"
            "Что делаешь?\n"
            "1. Открываешь письмо\n"
            "2. Спрашиваешь кто она\n"
            "3. Оглядываешься вокруг"
        ],
        visibility="public",
    )
    db.add(story)
    await db.flush()

    # Создаём снапшот персонажа
    snapshot = StoryCharacterSnapshot(
        story_id=story.id,
        character_id=character.id,
        snapshot_data={
            "name": character.name,
            "description_ai": character.description_ai,
            "example_dialogues": character.example_dialogues,
        }
    )
    db.add(snapshot)
    await db.commit()

    return story
