# Storyweave

AI-платформа для ролевых игр / интерактивной литературы в Telegram.

## Структура проекта

```
storyweave/
├── core/                    # Ядро — ноль Telegram-кода
│   ├── contracts.py         # Нейтральные контракты (IncomingEvent, OutgoingMessage)
│   ├── engine/              # Game Engine — логика обработки хода
│   ├── prompt/              # Сборка промптов для LLM
│   └── memory/              # Управление памятью сессии
│
├── adapters/
│   └── telegram/            # Единственное место с кодом Telegram
│       ├── inbound.py       # webhook → IncomingEvent
│       └── outbound.py      # OutgoingMessage → Telegram API
│
├── workers/
│   ├── text/                # Celery-воркеры для LLM (очередь: text)
│   └── image/               # Celery-воркеры для изображений (очередь: media)
│
├── infrastructure/
│   ├── db/                  # SQLAlchemy модели и подключение
│   ├── queue/               # Celery приложение
│   └── storage/             # S3-совместимый клиент (MinIO / R2)
│
└── config/
    └── settings.py          # Конфигурация через переменные окружения
```

## Быстрый старт

### 1. Клонировать и настроить окружение

```bash
cp .env.example .env
# Заполнить .env своими ключами
```

### 2. Поднять инфраструктуру

```bash
docker-compose up postgres redis minio -d
```

### 3. Запустить миграции

```bash
pip install -r requirements.txt
alembic upgrade head
```

### 4. Запустить бота локально (polling для разработки)

```bash
python -m adapters.telegram.bot
```

### 5. Запустить воркеры

```bash
# В отдельных терминалах:
celery -A infrastructure.queue.celery_app worker -Q text -c 5 --loglevel=info
celery -A infrastructure.queue.celery_app worker -Q media -c 3 --loglevel=info
```

### MinIO UI

Открыть http://localhost:9001 (minioadmin / minioadmin)

## Ключевые принципы

- **Ядро не знает про Telegram** — весь специфичный код только в `adapters/telegram/`
- **Две отдельные очереди** — медленная генерация изображений не блокирует текстовый ответ
- **MinIO локально = R2 на проде** — переключение через одну переменную окружения
- **Пользователь ≠ telegram_id** — идентификатор хранится в `PlatformAccount`, не в `User`
