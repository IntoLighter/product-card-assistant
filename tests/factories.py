"""Тестовые данные и заглушка LLM."""

import copy
from collections.abc import Sequence
from typing import Any, cast

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from core.models import Commercial, LLMDraft
from core.validation import RawProduct

_MANOMETER: dict[str, Any] = {
    "name": "Манометр показывающий DM 02",
    "manufacturer": "Манотомь",
    "specs": {
        "диапазон измерений": "0–1,6 МПа",
        "класс точности": "1,5",
        "присоединение": "G1/2",
        "диаметр корпуса": "100 мм",
    },
    "description": "Прибор предназначен для измерения избыточного давления.",
}

GOOD_DESCRIPTION = (
    "Манометр показывающий DM 02 производства Манотомь предназначен "
    "для измерения избыточного давления "
    "и визуального контроля его значения непосредственно на месте установки. "
) * 4 + (
    "Диапазон измерений 0–1,6 МПа, класс точности 1,5, "
    "присоединение G1/2, диаметр корпуса 100 мм. "
) * 2


def manometer_data() -> dict[str, Any]:
    """Свежая копия входного JSON: тесты могут менять вложенный specs."""
    return copy.deepcopy(_MANOMETER)


def manometer() -> RawProduct:
    return raw_product(manometer_data())


def raw_product(data: dict[str, Any]) -> RawProduct:
    """Товар из словаря в формате входного JSON."""
    return RawProduct.model_validate(data)


def make_draft(**overrides: object) -> LLMDraft:
    """
    Корректный ответ модели.

    overrides подменяют поля без валидации — так получаются «плохие» ответы.
    """
    draft = LLMDraft(
        seo_title="Манометр показывающий DM 02 Манотомь, 0–1,6 МПа",
        seo_description=GOOD_DESCRIPTION,
        search_queries=["манометр dm 02", "манометр манотомь", "манометр 1,6 мпа"],
        commercial=Commercial(
            audience=["службы КИПиА"],
            tasks=["контроль давления"],
            pitch="Простой показывающий прибор для контроля давления.",
        ),
    )
    return draft.model_copy(update=overrides)


class FakeLLM:
    """Отдаёт заготовленные ответы по очереди и запоминает запросы."""

    model_name = "fake-llm"

    def __init__(self, *responses: LLMDraft | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[list[ChatCompletionMessageParam]] = []
        self.attempts: list[int] = []

    def generate[T: BaseModel](
        self,
        messages: Sequence[ChatCompletionMessageParam],
        response_model: type[T],
        *,
        attempt: int = 0,
    ) -> T:
        assert response_model is LLMDraft
        self.calls.append(list(messages))
        self.attempts.append(attempt)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return cast("T", response)
