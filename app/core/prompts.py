"""
Сообщения для LLM, собранные из шаблонов в prompt_templates/.

Тексты промптов лежат отдельными файлами, чтобы их можно было читать и править,
не трогая код. Подстановки делает string.Template ($name), а ограничения из ТЗ
берутся из models, поэтому промпт и проверка ответа не расходятся.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING

from .models import (
    CLARIFICATIONS_MAX,
    COMMERCIAL_ITEMS_MAX,
    DESCRIPTION_MAX_LEN,
    DESCRIPTION_MIN_LEN,
    MISSING,
    QUERIES_MAX,
    QUERIES_MIN,
    TITLE_MAX_LEN,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from openai.types.chat import ChatCompletionMessageParam

    from .models import Issue, ProductInput
    from .profiles import Profile

TEMPLATES_DIR = Path(__file__).parent / "prompt_templates"


def build_messages(product: ProductInput, profile: Profile, missing: list[str]) -> list[ChatCompletionMessageParam]:
    """Первый запрос: системные правила и данные о товаре."""
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": user_prompt(product, profile, missing)},
    ]


def build_fix_messages(
    messages: Sequence[ChatCompletionMessageParam], previous_answer: str, problems: list[Issue]
) -> list[ChatCompletionMessageParam]:
    """Повторный запрос: исходный диалог, прошлый ответ модели и конкретные замечания проверки."""
    fix_request = _template("fix").substitute(problems=_bullets(problem.message for problem in problems))
    return [
        *messages,
        {"role": "assistant", "content": previous_answer},
        {"role": "user", "content": fix_request},
    ]


def system_prompt() -> str:
    return _template("system").substitute(
        title_max=TITLE_MAX_LEN,
        description_min=DESCRIPTION_MIN_LEN,
        description_max=DESCRIPTION_MAX_LEN,
        queries_min=QUERIES_MIN,
        queries_max=QUERIES_MAX,
        commercial_max=COMMERCIAL_ITEMS_MAX,
        clarifications_max=CLARIFICATIONS_MAX,
    )


def user_prompt(product: ProductInput, profile: Profile, missing: list[str]) -> str:
    data = {
        "название": product.name,
        "производитель": product.manufacturer or MISSING,
        "характеристики": product.specs or MISSING,
        "описание": product.description or MISSING,
    }
    return _template("user").substitute(
        data=json.dumps(data, ensure_ascii=False, indent=2),
        category=profile.title,
        missing=_bullets(missing) or "- (нет)",
    )


@cache
def _template(name: str) -> Template:
    return Template((TEMPLATES_DIR / f"{name}.txt").read_text(encoding="utf-8"))


def _bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
