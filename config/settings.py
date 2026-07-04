"""
Конфигурация через переменные окружения.
Используем pydantic-settings для валидации.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://isekai:isekai@localhost:5432/isekai"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Telegram
    telegram_bot_token: str = Field(default="")
    telegram_webhook_secret: str = Field(default="changeme")

    # LLM провайдеры
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    default_llm_provider: str = Field(default="openai")  # openai | anthropic
    openai_base_url: str = Field(default="https://api.openai.com/v1")

    # Image провайдеры
    runware_api_key: str = Field(default="")
    fal_api_key: str = Field(default="")
    default_image_provider: str = Field(default="runware")  # runware | fal

    # Storage (S3-совместимый: MinIO локально, R2 на проде)
    storage_endpoint_url: str = Field(default="http://localhost:9000")
    storage_access_key: str = Field(default="minioadmin")
    storage_secret_key: str = Field(default="minioadmin")
    storage_bucket: str = Field(default="storyweave-assets")
    storage_public_url: str = Field(default="http://localhost:9000/storyweave-assets")

    # Приложение
    debug: bool = Field(default=False)
    webhook_base_url: str = Field(default="")  # https://yourdomain.com

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
