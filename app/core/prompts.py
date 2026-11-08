"""
Сообщения для LLM, собранные из шаблонов в resources/prompts/.

Тексты промптов лежат отдельными файлами, чтобы их можно было читать и править,
не трогая код. Подстановки делает string.Template ($name), а ограничения из ТЗ
берутся из models, поэтому промпт и проверка ответа не расходятся.
"""

import json
from collections.abc import Iterable, Sequence
from string import Template

from openai.types.chat import ChatCompletionMessageParam

from core.models import (
    COMMERCIAL_ITEMS_MAX,
    DESCRIPTION_MAX_LEN,
    DESCRIPTION_MIN_LEN,
    MISSING,
    QUERIES_MAX,
    QUERIES_MIN,
    TITLE_MAX_LEN,
    Issue,
    ProductInput,
)
from core.resources import prompts_dir
from core.templates import ProductTemplate


def build_messages(
    product: ProductInput, template: ProductTemplate, missing: list[str]
) -> list[ChatCompletionMessageParam]:
    """Первый запрос: системные правила и данные о товаре."""
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": user_prompt(product, template, missing)},
    ]


def build_fix_messages(
    messages: Sequence[ChatCompletionMessageParam],
    previous_answer: str,
    problems: list[Issue],
) -> list[ChatCompletionMessageParam]:
    """
    Повторный запрос на исправление.

    Исходный диалог, прошлый ответ модели и конкретные замечания проверки.
    """
    fix_request = _template("fix").substitute(
        problems=_bullets(problem.message for problem in problems)
    )
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
    )


def user_prompt(
    product: ProductInput, template: ProductTemplate, missing: list[str]
) -> str:
    data = {
        "название": product.name,
        "производитель": product.manufacturer or MISSING,
        "характеристики": product.specs or MISSING,
        "описание": product.description or MISSING,
    }
    return _template("user").substitute(
        data=json.dumps(data, ensure_ascii=False, indent=2),
        category=template.category,
        missing=_bullets(missing) or "- (нет)",
    )


def _template(name: str) -> Template:
    # Без кэша: правки шаблонов видны сразу, без перезапуска; файлы крошечные
    return Template((prompts_dir() / f"{name}.txt").read_text(encoding="utf-8"))


def _bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
