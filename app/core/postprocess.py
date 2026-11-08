"""
Безопасные правки ответа модели кодом.

Здесь только то, что не может добавить фактов: например, удаление лишних предложений.
"""

import re

from core.models import DESCRIPTION_MAX_LEN, DESCRIPTION_MIN_LEN, LLMDraft

SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+")


def fit_draft(draft: LLMDraft) -> LLMDraft:
    """Ответ модели с описанием, подогнанным под максимальную длину."""
    description = fit_description(draft.seo_description)
    if description == draft.seo_description:
        return draft
    return draft.model_copy(update={"seo_description": description})


def fit_description(
    text: str, max_len: int = DESCRIPTION_MAX_LEN, min_len: int = DESCRIPTION_MIN_LEN
) -> str:
    """
    Убирает последние предложения, пока описание не уложится в max_len.

    Модели при просьбе «дописать» часто проскакивают верхнюю границу; отрезать
    предложения надёжнее, чем просить модель сократить текст. Если после обрезки
    текст стал бы короче min_len, он возвращается без изменений.
    """
    if len(text) <= max_len:
        return text

    paragraphs = [
        SENTENCE_BREAK.split(paragraph.strip())
        for paragraph in text.split("\n\n")
        if paragraph.strip()
    ]

    while paragraphs and len(_join(paragraphs)) > max_len:
        paragraphs[-1].pop()
        if not paragraphs[-1]:
            paragraphs.pop()

    fitted = _join(paragraphs)
    return fitted if len(fitted) >= min_len else text


def _join(paragraphs: list[list[str]]) -> str:
    return "\n\n".join(" ".join(sentences) for sentences in paragraphs)
