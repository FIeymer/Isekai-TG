from openai import AsyncOpenAI
from config.settings import settings

client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
)

SYSTEM_PROMPT = """Ты — ведущий интерактивной ролевой игры.
Веди историю последовательно, помни всё что происходило раньше.
Когда игрок выбирает вариант (1, 2, 3) — продолжай именно ту ветку которую он выбрал.
Отвечай на том же языке что и игрок. Предлагай 2-3 варианта действий в конце каждого хода."""

# Простое хранилище истории в памяти: session_id -> list of messages
_history: dict[str, list[dict]] = {}


async def generate_text(session_id: str, user_message: str) -> str:
    if session_id not in _history:
        _history[session_id] = []

    _history[session_id].append({"role": "user", "content": user_message})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _history[session_id]

    response = await client.chat.completions.create(
        model="openrouter/auto",
        messages=messages,
        max_tokens=500,
    )

    reply = response.choices[0].message.content
    _history[session_id].append({"role": "assistant", "content": reply})

    return reply
