import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import Story, Character, StoryCharacterSnapshot, User, Visibility

logger = logging.getLogger(__name__)


async def get_public_stories(db: AsyncSession) -> list[Story]:
    """Все публичные истории — для /play."""
    result = await db.execute(
        select(Story)
        .where(Story.visibility == Visibility.PUBLIC)
        .order_by(Story.created_at.desc())
        .limit(10)
    )
    return result.scalars().all()


async def get_user_stories(db: AsyncSession, author: User) -> list[Story]:
    """Личные истории пользователя — для /mystories."""
    result = await db.execute(
        select(Story)
        .where(Story.author_id == author.id)
        .order_by(Story.created_at.desc())
    )
    return result.scalars().all()


async def get_story_by_id(db: AsyncSession, story_id: str) -> Story | None:
    result = await db.execute(
        select(Story).where(Story.id == story_id)
    )
    return result.scalar_one_or_none()


async def get_story_snapshot(db: AsyncSession, story_id: str) -> StoryCharacterSnapshot | None:
    result = await db.execute(
        select(StoryCharacterSnapshot)
        .where(StoryCharacterSnapshot.story_id == story_id)
    )
    return result.scalar_one_or_none()


async def publish_story(db: AsyncSession, story_id: str, author: User) -> bool:
    """Опубликовать историю. Возвращает True если успешно."""
    result = await db.execute(
        select(Story).where(
            Story.id == story_id,
            Story.author_id == author.id,
        )
    )
    story = result.scalar_one_or_none()
    if not story:
        return False

    story.visibility = Visibility.PUBLIC
    await db.commit()
    return True


async def delete_story(db: AsyncSession, story_id: str, author: User) -> bool:
    """Удалить историю пользователя. Возвращает True если успешно."""
    result = await db.execute(
        select(Story).where(
            Story.id == story_id,
            Story.author_id == author.id,
        )
    )
    story = result.scalar_one_or_none()
    if not story:
        return False

    await db.execute(
        delete(StoryCharacterSnapshot).where(
            StoryCharacterSnapshot.story_id == story.id
        )
    )
    await db.execute(
        delete(Story).where(Story.id == story.id)
    )
    await db.commit()
    return True


async def create_demo_story(db: AsyncSession, author: User) -> tuple[Story, bool]:
    """
    Создать демо-историю как личную (private).
    Если уже есть — вернуть существующую.
    Возвращает (история, создана_ли_новая).
    """
    result = await db.execute(
        select(Story).where(
            Story.author_id == author.id,
            Story.title == 'Проклятие Тёмного леса',
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False

    character = Character(
        author_id=author.id,
        name='Эльяра',
        description_player='Таинственная эльфийская волшебница с тёмным прошлым.',
        description_ai=(
            'Ты — Эльяра, эльфийская волшебница 300 лет от роду. '
            'Ты говоришь загадочно и мудро, иногда цитируешь древние пророчества. '
            'Ты помогаешь герою, но скрываешь свои истинные мотивы. '
            'Никогда не выходи из образа.'
        ),
        example_dialogues=(
            'Герой: Кто ты?\n'
            'Эльяра: Я — лишь тень прошлого, странник. Вопрос не в том, кто я, '
            'а в том, готов ли ты узнать правду о себе.'
        ),
        visibility=Visibility.PRIVATE,
    )
    db.add(character)
    await db.flush()

    story = Story(
        author_id=author.id,
        title='Проклятие Тёмного леса',
        plot_summary_player=(
            'Ты просыпаешься у костра на опушке зловещего леса. '
            'Рядом — запечатанное письмо с твоим именем...'
        ),
        plot_ai=(
            'Действие происходит в тёмном фэнтезийном мире. '
            'Герой — искатель приключений без памяти о прошлом. '
            'Главная тайна: герой является последним хранителем древней магии. '
            'Эльяра знает правду, но открывает её постепенно. '
            'Веди историю в сторону раскрытия тайны прошлого героя.'
        ),
        ai_reminder=(
            'Ты играешь Эльяру. Веди историю в образе, '
            'предлагай 2-3 варианта действий в конце каждого хода.'
        ),
        first_messages=[
            'Ты приходишь в себя у догорающего костра. Тёмный лес окружает тебя со всех сторон.\n\n'
            'Из теней выступает фигура в тёмном плаще.\n\n'
            '— Наконец-то ты проснулся, — говорит незнакомка. — Времени мало. Они уже идут.\n\n'
            'Что делаешь?\n'
            '1. Открываешь письмо\n'
            '2. Спрашиваешь кто она\n'
            '3. Оглядываешься вокруг'
        ],
        visibility=Visibility.PRIVATE,  # создаётся как личная
    )
    db.add(story)
    await db.flush()

    snapshot = StoryCharacterSnapshot(
        story_id=story.id,
        character_id=character.id,
        snapshot_data={
            'name': character.name,
            'description_ai': character.description_ai,
            'example_dialogues': character.example_dialogues,
        }
    )
    db.add(snapshot)
    await db.commit()

    return story, True