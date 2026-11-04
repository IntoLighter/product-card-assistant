"""Настройки из переменных окружения (.env подхватывается автоматически)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    base_url: str = "http://localhost:8000/v1"
    model: str = "local-model"
    api_key: str = "EMPTY"
    temperature: float = 0.3
    seed: int = 42
    timeout: float = 120.0
    max_attempts: int = 3  # 1 генерация + до 2 исправлений по замечаниям проверки

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        return cls(
            base_url=os.getenv("LLM_BASE_URL", cls.base_url),
            model=os.getenv("LLM_MODEL", cls.model),
            api_key=os.getenv("LLM_API_KEY", cls.api_key) or cls.api_key,
            temperature=_float("TEMPERATURE", cls.temperature),
            seed=_int("SEED", cls.seed),
            timeout=_float("REQUEST_TIMEOUT", cls.timeout),
            max_attempts=max(1, _int("MAX_ATTEMPTS", cls.max_attempts)),
        )
