"""
Настройки из переменных окружения (pydantic-settings).

Значения по умолчанию лежат в одном месте — в файле .env в корне проекта (он
хранится в git), ключи и токены — в .env_secrets (вне git). Приоритет: переменные
окружения (например, из docker compose) > .env_secrets > .env. Без нужной
переменной или с некорректным значением Settings() падает с ValidationError,
где перечислены все проблемные поля.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> корень проекта: файлы находятся независимо от текущей папки
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Параметры подключения к LLM и генерации."""

    model_config = SettingsConfigDict(
        # Более поздний файл перекрывает более ранний; отсутствующие файлы пропускаются
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / ".env_secrets"),
        env_file_encoding="utf-8",
        # В .env есть и настройки vLLM и Streamlit — приложению они не нужны
        extra="ignore",
        frozen=True,
        # Имена полей — для кода и тестов, алиасы — имена переменных окружения
        validate_by_name=True,
    )

    base_url: str = Field(validation_alias="LLM_BASE_URL")
    model: str = Field(validation_alias="LLM_MODEL")
    api_key: str = Field(validation_alias="LLM_API_KEY")
    temperature: float = Field(validation_alias="TEMPERATURE", ge=0, le=2)
    seed: int = Field(validation_alias="SEED")
    timeout: float = Field(validation_alias="REQUEST_TIMEOUT", gt=0)
    # Первая генерация и исправления по замечаниям проверки
    max_attempts: int = Field(validation_alias="MAX_ATTEMPTS", ge=1)
