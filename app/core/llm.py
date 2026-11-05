"""
Клиент LLM через OpenAI-совместимый API (vLLM, Ollama, llama-server, облако).

Ответ ограничивается JSON-схемой pydantic-модели (structured output), поэтому
сервер не даст модели вернуть невалидный JSON или лишние поля.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, NamedTuple, Protocol

import openai
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

    from .config import Settings

MAX_COMPLETION_TOKENS = 2048
HEALTH_CHECK_TIMEOUT_SECONDS = 3
# Повторы на уровне SDK: обрывы соединения, 429 и 5xx
TRANSPORT_RETRIES = 2


class LLMError(Exception):
    """Сбой связи или сервера: повтор генерации не поможет, нужно сообщить пользователю."""


class LLMOutputError(Exception):
    """Модель вернула невалидный ответ: имеет смысл сгенерировать заново."""


class ServerStatus(NamedTuple):
    ready: bool
    message: str


class LLMClient(Protocol):
    """То, что пайплайну нужно от LLM; в тестах подменяется заглушкой."""

    @property
    def model_name(self) -> str: ...

    def generate[T: BaseModel](
        self, messages: Sequence[ChatCompletionMessageParam], response_model: type[T], *, attempt: int = 0
    ) -> T:
        """
        Ответ модели, разобранный в response_model.

        attempt сдвигает seed: при фиксированном seed повтор того же запроса дал бы тот же ответ.
        """
        ...


class OpenAICompatibleClient:
    """Реализация LLMClient поверх OpenAI SDK."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = openai.OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=settings.timeout,
            max_retries=TRANSPORT_RETRIES,
        )

    @property
    def model_name(self) -> str:
        return self.settings.model

    def generate[T: BaseModel](
        self, messages: Sequence[ChatCompletionMessageParam], response_model: type[T], *, attempt: int = 0
    ) -> T:
        try:
            response = self._client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
                temperature=self.settings.temperature,
                seed=self.settings.seed + attempt,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "schema": response_model.model_json_schema(),
                        "strict": True,
                    },
                },
                # Qwen3/3.5: без режима рассуждений ответ быстрее, а копирайтингу он не нужен
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        except openai.APIError as error:
            raise LLMError(describe_api_error(error, self.settings)) from error
        return parse_response(response, response_model)

    def check_server(self) -> ServerStatus:
        """Готов ли сервер отвечать: для индикатора в интерфейсе и проверки перед пакетным запуском."""
        try:
            models = self._client.with_options(timeout=HEALTH_CHECK_TIMEOUT_SECONDS, max_retries=0).models.list()
        except openai.APIError:
            return ServerStatus(
                ready=False,
                message=f"LLM-сервер недоступен ({self.settings.base_url}): "
                "модель ещё загружается или контейнер не запущен.",
            )
        available = [model.id for model in models.data]
        if self.settings.model not in available:
            return ServerStatus(
                ready=False,
                message=f"Сервер доступен, но модели «{self.settings.model}» на нём нет. "
                f"Доступны: {', '.join(available) or '—'}.",
            )
        return ServerStatus(ready=True, message=f"Модель «{self.settings.model}» готова.")


def parse_response[T: BaseModel](response: ChatCompletion, response_model: type[T]) -> T:
    """Текст ответа -> response_model; любые отклонения — LLMOutputError, чтобы пайплайн повторил запрос."""
    if not response.choices:
        raise LLMOutputError("пустой ответ модели")
    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise LLMOutputError("ответ обрезан по лимиту токенов")
    try:
        return response_model.model_validate_json(choice.message.content or "")
    except ValidationError as error:
        raise LLMOutputError(f"ответ не соответствует схеме ({error.error_count()} ошибок)") from error


def describe_api_error(error: openai.APIError, settings: Settings) -> str:
    """Понятное пользователю описание сбоя API с подсказкой, что проверить."""
    if isinstance(error, openai.APITimeoutError):
        return f"LLM не ответила за {settings.timeout:.0f} с. Попробуйте ещё раз или увеличьте REQUEST_TIMEOUT."
    if isinstance(error, openai.APIConnectionError):
        return (
            f"Нет связи с LLM-сервером ({settings.base_url}). Проверьте, что контейнер vllm запущен "
            "(docker compose ps): первая загрузка модели занимает несколько минут."
        )
    if isinstance(error, openai.APIStatusError):
        known_statuses: dict[int, str] = {
            HTTPStatus.UNAUTHORIZED: "LLM-сервер отклонил ключ доступа (LLM_API_KEY).",
            HTTPStatus.NOT_FOUND: f"Модель «{settings.model}» не найдена на сервере. Проверьте LLM_MODEL.",
            HTTPStatus.BAD_REQUEST: f"LLM-сервер отклонил запрос: {error.message}",
        }
        fallback = f"Ошибка LLM-сервера (HTTP {error.status_code}): {error.message}"
        return known_statuses.get(error.status_code, fallback)
    return f"Ошибка обращения к LLM: {error.message}"
