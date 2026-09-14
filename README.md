# Storyweave

AI-платформа для ролевых игр / интерактивной литературы в Telegram.

## Структура проекта

```
storyweave/
├── core/                    # Ядро — ноль Telegram-кода
│   ├── contracts.py         # Нейтральные контракты (IncomingEvent, OutgoingMessage)
│   ├── engine/
│   │   ├── handler.py       # Обработка входящего события
│   │   └── llm.py           # Клиент LLM с историей и блокировкой
│   ├── prompt/              # Сборка промптов (в разработке)
│   └── memory/              # Управление памятью сессии (в разработке)
│
├── adapters/
│   └── telegram/
│       └── bot.py           # Единственное место с кодом Telegram
│
├── workers/
│   ├── text/                # Celery-воркеры для LLM (в разработке)
│   └── image/               # Celery-воркеры для изображений (в разработке)
│
├── infrastructure/
│   ├── db/
│   │   ├── models.py        # SQLAlchemy модели
│   │   └── connection.py    # Подключение к БД
│   ├── queue/
│   │   └── celery_app.py    # Celery приложение
│   └── storage/
│       └── client.py        # S3-совместимый клиент (MinIO / R2)
│
├── migrations/              # Alembic миграции
├── config/
│   └── settings.py          # Конфигурация через переменные окружения
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone <repo_url>
cd storyweave
```

### 2. Создать и заполнить .env

```bash
cp .env.example .env
```

Заполнить в `.env`:
- `TELEGRAM_BOT_TOKEN` — получить у [@BotFather](https://t.me/BotFather)
- `OPENAI_API_KEY` — ключ от [OpenRouter](https://openrouter.ai/keys)

### 3. Поднять инфраструктуру

```bash
docker-compose up postgres redis minio -d
```

### 4. Создать виртуальное окружение и установить зависимости

**Mac / Linux:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install psycopg2-binary  # для Alembic
```

**Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install psycopg2-binary
```

### 5. Применить миграции

**Mac / Linux:**
```bash
PYTHONPATH=. alembic upgrade head
```

**Windows:**
```powershell
$env:PYTHONPATH = "."
alembic upgrade head
```

### 6. Запустить бота

**Mac / Linux:**
```bash
PYTHONPATH=. .venv/bin/python -m adapters.telegram.bot
```

**Windows:**
```powershell
$env:PYTHONPATH = "."
python -m adapters.telegram.bot
```

## Сервисы

| Сервис | URL | Назначение |
|--------|-----|------------|
| MinIO UI | http://localhost:9001 | Управление файлами (minioadmin / minioadmin) |
| PostgreSQL | localhost:5432 | База данных |
| Redis | localhost:6379 | Брокер очередей |

## Ключевые принципы

- **Ядро не знает про Telegram** — весь специфичный код только в `adapters/telegram/`
- **Пользователь ≠ telegram_id** — идентификатор хранится в `PlatformAccount`, не в `User`
- **История переживает рестарт** — загружается из БД при первом обращении к сессии
- **Ошибки LLM не попадают в контекст** — при ошибке откатываем сообщение из истории
- **MinIO локально = R2 на проде** — переключение через одну переменную окружения

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `DATABASE_URL` | URL PostgreSQL |
| `REDIS_URL` | URL Redis |
| `TELEGRAM_BOT_TOKEN` | Токен бота от BotFather |
| `OPENAI_API_KEY` | Ключ OpenAI или OpenRouter |
| `OPENAI_BASE_URL` | Base URL (для OpenRouter: `https://openrouter.ai/api/v1`) |
| `STORAGE_ENDPOINT_URL` | URL MinIO (локально) или R2 (прод) |
| `STORAGE_ACCESS_KEY` | Ключ доступа к хранилищу |
| `STORAGE_SECRET_KEY` | Секретный ключ хранилища |
| `STORAGE_BUCKET` | Название бакета |
| `STORAGE_PUBLIC_URL` | Публичный URL для доступа к файлам |