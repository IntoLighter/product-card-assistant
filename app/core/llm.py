"""Клиент LLM через OpenAI-совместимый API (vLLM, Ollama, llama-server, облако)."""

from __future__ import annotations

import json
from typing import Protocol

import openai

from .config import Settings


class LLMError(Exception):
    """Сбой связи/сервера — повтор генерации не поможет, нужно показать пользователю."""


class LLMOutputError(Exception):
    """Модель вернула невалидный ответ — имеет смысл повторить."""


class LLMClient(Protocol):
    def complete_json(self, messages: list[dict], schema: dict, attempt: int = 0) -> tuple[dict, str]:
        """Возвращает (распарсенный JSON, сырой текст ответа).

        attempt сдвигает seed: при фиксированном seed повтор того же запроса дал бы тот же ответ.
        """
        ...


class OpenAICompatibleClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = openai.OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=settings.timeout,
            max_retries=2,  # SDK сам повторяет 429/5xx/обрывы с паузой
        )

    def complete_json(self, messages: list[dict], schema: dict, attempt: int = 0) -> tuple[dict, str]:
        s = self.settings
        try:
            resp = self._client.chat.completions.create(
                model=s.model,
                messages=messages,
                temperature=s.temperature,
                seed=s.seed + attempt,
                max_tokens=2048,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "product_card", "schema": schema, "strict": True},
                },
                # Qwen3/3.5: без режима рассуждений — быстрее, а для копирайтинга он не нужен
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        except openai.APITimeoutError as e:
            raise LLMError(f"LLM не ответила за {s.timeout:.0f} с. Попробуйте ещё раз "
                           "или увеличьте REQUEST_TIMEOUT.") from e
        except openai.APIConnectionError as e:
            raise LLMError(f"Нет связи с LLM-сервером ({s.base_url}). Проверьте, что контейнер vllm "
                           "запущен: docker compose ps. Первая загрузка модели занимает несколько минут.") from e
        except openai.AuthenticationError as e:
            raise LLMError("LLM-сервер отклонил ключ доступа (LLM_API_KEY).") from e
        except openai.NotFoundError as e:
            raise LLMError(f"Модель «{s.model}» не найдена на сервере. Проверьте LLM_MODEL.") from e
        except openai.BadRequestError as e:
            raise LLMError(f"LLM-сервер отклонил запрос: {e.message}") from e
        except openai.APIStatusError as e:
            raise LLMError(f"Ошибка LLM-сервера (HTTP {e.status_code}): {e.message}") from e

        if not resp.choices:
            raise LLMOutputError("пустой ответ модели")
        choice = resp.choices[0]
        text = choice.message.content or ""
        if choice.finish_reason == "length":
            raise LLMOutputError("ответ обрезан по лимиту токенов")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMOutputError(f"ответ не является JSON: {e.msg}") from e
        if not isinstance(data, dict):
            raise LLMOutputError("ответ не является JSON-объектом")
        return data, text

    def health(self) -> tuple[bool, str]:
        """Быстрая проверка готовности сервера для UI."""
        try:
            models = self._client.with_options(timeout=3, max_retries=0).models.list()
        except openai.APIError:
            return False, f"LLM-сервер недоступен ({self.settings.base_url}): модель ещё загружается или контейнер не запущен."
        ids = [m.id for m in models.data]
        if self.settings.model not in ids:
            return False, f"Сервер доступен, но модели «{self.settings.model}» нет. Доступны: {', '.join(ids) or '—'}"
        return True, f"Модель «{self.settings.model}» готова"
