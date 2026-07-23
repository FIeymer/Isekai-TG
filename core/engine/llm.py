import logging
from openai import AsyncOpenAI
from redis.asyncio import Redis
from config.settings import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
)

redis = Redis.from_url(settings.redis_url, decode_responses=True)

SYSTEM_PROMPT = """Ты — ведущий интерактивной ролевой игры.
Веди историю последовательно, помни всё что происходило раньше.
Когда игрок выбирает вариант (1, 2, 3) — продолжай именно ту ветку которую он выбрал.
Отвечай на том же языке что и игрок. Предлагай 2-3 варианта действий в конце каждого хода."""

# Локальный кэш истории: session_id -> list of messages
_history: dict[str, list[dict]] = {}

LOCK_TTL = 60  # секунд — автоматически снимается если процесс упал


async def _acquire_lock(session_id: str) -> bool:
    """Попытаться захватить блокировку через Redis. Возвращает True если успешно."""
    key = f"lock:session:{session_id}"
    result = await redis.set(key, "1", nx=True, ex=LOCK_TTL)
    return result is not None


async def _release_lock(session_id: str):
    """Снять блокировку."""
    await redis.delete(f"lock:session:{session_id}")


async def generate_text(session_id: str, user_message: str) -> str:
    # Блокируем параллельные запросы — работает между процессами через Redis
    if not await _acquire_lock(session_id):
        return "⏳ Подожди, я ещё думаю над предыдущим ответом..."

    if session_id not in _history:
        _history[session_id] = []

    _history[session_id].append({"role": "user", "content": user_message})

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _history[session_id]

        response = await client.chat.completions.create(
            model="openrouter/auto",
            messages=messages,
            max_tokens=500,
        )

        reply = response.choices[0].message.content
        _history[session_id].append({"role": "assistant", "content": reply})

        return reply

    except Exception as e:
        logger.error(f"LLM error for session {session_id}: {e}")
        # Откатываем сообщение пользователя — не засоряем историю
        _history[session_id].pop()
        return "⚠️ Что-то пошло не так. Попробуй ещё раз."

    finally:
        await _release_lock(session_id)