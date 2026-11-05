"""Карточка в виде, удобном для копирования: Markdown и JSON."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import DESCRIPTION_MAX_LEN, DESCRIPTION_MIN_LEN, TITLE_MAX_LEN

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import ProductCard


def to_markdown(card: ProductCard) -> str:
    sections = [
        f"# {card.product_name}",
        _check_warnings(card),
        f"**Категория:** {card.category}",
        _seo(card),
        _specs_table(card),
        _section("Поисковые запросы", _bullets(card.search_queries)),
        _commercial(card),
        _section("Требует уточнения", _bullets(card.needs_clarification)) if card.needs_clarification else "",
        _footer(card),
    ]
    return "\n\n".join(section for section in sections if section) + "\n"


def to_json(card: ProductCard) -> str:
    return card.model_dump_json(indent=2) + "\n"


def _check_warnings(card: ProductCard) -> str:
    if not card.check_warnings:
        return ""
    lines = ["**Автоматическая проверка нашла замечания — просмотрите их перед публикацией:**", ""]
    lines += [f"- {warning.message}" for warning in card.check_warnings]
    return "\n".join(f"> {line}".rstrip() for line in lines)


def _seo(card: ProductCard) -> str:
    title_heading = f"SEO-заголовок ({card.meta.seo_title_length} из {TITLE_MAX_LEN} символов)"
    description_heading = (
        f"SEO-описание ({card.meta.seo_description_length} символов, норма {DESCRIPTION_MIN_LEN}–{DESCRIPTION_MAX_LEN})"
    )
    return "\n\n".join([_section(title_heading, card.seo_title), _section(description_heading, card.seo_description)])


def _specs_table(card: ProductCard) -> str:
    rows = [f"| {_table_cell(spec.name)} | {_table_cell(spec.value)} |" for spec in card.specs]
    return _section("Ключевые характеристики", "\n".join(["| Характеристика | Значение |", "| --- | --- |", *rows]))


def _commercial(card: ProductCard) -> str:
    commercial = card.commercial
    parts = [
        _section("Кому подходит", _bullets(commercial.audience), level=3),
        _section("Какие задачи решает", _bullets(commercial.tasks), level=3),
        _section("Как предложить клиенту", commercial.pitch, level=3),
    ]
    return _section("Для менеджера", "\n\n".join(parts))


def _footer(card: ProductCard) -> str:
    return (
        "---\n\n"
        f"_Черновик сгенерирован моделью {card.meta.llm_model}, попыток генерации: {card.meta.attempts}. "
        "Технические значения взяты только из входных данных._"
    )


def _section(heading: str, body: str, *, level: int = 2) -> str:
    return f"{'#' * level} {heading}\n\n{body}"


def _bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
