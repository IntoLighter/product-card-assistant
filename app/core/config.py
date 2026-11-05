"""Настройки из переменных окружения; файл .env подхватывается автоматически."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """Параметры подключения к LLM и генерации."""

    base_url: str = "http://localhost:8000/v1"
    model: str = "local-model"
    # vLLM без --api-key ключ не проверяет, но SDK требует непустое значение
    api_key: str = "EMPTY"
    temperature: float = 0.3
    seed: int = 42
    timeout: float = 120.0
    # Первая генерация и до двух исправлений по замечаниям проверки
    max_attempts: int = 3

    @classmethod
    def from_env(cls) -> Settings:
        """Читает настройки из окружения; некорректные числа заменяются значениями по умолчанию."""
        load_dotenv()
        defaults = cls()
        return cls(
            base_url=os.getenv("LLM_BASE_URL") or defaults.base_url,
            model=os.getenv("LLM_MODEL") or defaults.model,
            api_key=os.getenv("LLM_API_KEY") or defaults.api_key,
            temperature=_env_number("TEMPERATURE", defaults.temperature, float),
            seed=_env_number("SEED", defaults.seed, int),
            timeout=_env_number("REQUEST_TIMEOUT", defaults.timeout, float),
            max_attempts=max(1, _env_number("MAX_ATTEMPTS", defaults.max_attempts, int)),
        )


def _env_number[T: (int, float)](name: str, default: T, parse: Callable[[str], T]) -> T:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return parse(raw)
    except ValueError:
        log.warning("Некорректное значение %s=%r, используется %s", name, raw, default)
        return default
