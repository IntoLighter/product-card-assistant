"""
Настройки из переменных окружения (pydantic-settings).

Настройки лежат в одном месте — в файле .env в корне проекта (он хранится
в git), ключи и токены — в .env.local (вне git). Приоритет: переменные
окружения (например, из docker compose) > .env.local > .env. Без нужной
переменной или с некорректным значением Settings() падает с ValidationError,
где перечислены все проблемные поля.

Консольный режим работает вне Docker, поэтому поверх .env читает .env.cli
(тоже в git) — там только то, что отличается, например адрес vLLM.
"""

from pathlib import Path
from typing import Self

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> корень проекта: файлы находятся независимо от текущей папки
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
CLI_ENV_FILE = PROJECT_ROOT / ".env.cli"
LOCAL_ENV_FILE = PROJECT_ROOT / ".env.local"


class Settings(BaseSettings):
    """Параметры подключения к LLM и генерации."""

    model_config = SettingsConfigDict(
        # Более поздний файл перекрывает более ранний; отсутствующие файлы пропускаются
        env_file=(ENV_FILE, LOCAL_ENV_FILE),
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

    @classmethod
    def for_cli(cls) -> Self:
        """Настройки консольного режима: .env, поверх него .env.cli, затем секреты."""
        return cls(_env_file=(ENV_FILE, CLI_ENV_FILE, LOCAL_ENV_FILE))
