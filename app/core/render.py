"""Карточка в виде, удобном для копирования: обычный текст, Markdown и JSON."""

from collections.abc import Iterable

from core.models import ProductCard

TITLE_HEADING = "SEO-заголовок"
DESCRIPTION_HEADING = "SEO-описание"
WARNINGS_INTRO = (
    "**Автоматическая проверка нашла замечания — просмотрите их перед публикацией:**"
)


def to_markdown(card: ProductCard) -> str:
    sections = [
        f"# {card.product_name}",
        _check_warnings(card),
        f"**Категория:** {card.category}",
        _seo(card),
        _specs_table(card),
        _section("Поисковые запросы", _bullets(card.search_queries)),
        _commercial(card),
        _section("Требует уточнения", _bullets(card.needs_clarification))
        if card.needs_clarification
        else "",
    ]
    return "\n\n".join(section for section in sections if section) + "\n"


def to_text(card: ProductCard) -> str:
    """Обычный текст без разметки: чтобы вставить куда угодно, например в CMS."""
    commercial = card.commercial
    manager_notes = [
        f"Кому подходит:\n{_bullets(commercial.audience)}",
        f"Какие задачи решает:\n{_bullets(commercial.tasks)}",
        f"Как предложить клиенту: {commercial.pitch}",
    ]
    warnings = _bullets(warning.message for warning in card.check_warnings)
    sections = [
        card.product_name,
        _text_section("Замечания автоматической проверки", warnings)
        if warnings
        else "",
        f"Категория: {card.category}",
        _text_section(TITLE_HEADING, card.seo_title),
        _text_section(DESCRIPTION_HEADING, card.seo_description),
        _text_section(
            "Ключевые характеристики",
            "\n".join(f"{spec.name}: {spec.value}" for spec in card.specs),
        ),
        _text_section("Поисковые запросы", _bullets(card.search_queries)),
        _text_section("Для менеджера", "\n\n".join(manager_notes)),
        _text_section("Требует уточнения", _bullets(card.needs_clarification))
        if card.needs_clarification
        else "",
    ]
    return "\n\n".join(section for section in sections if section) + "\n"


def to_json(card: ProductCard) -> str:
    return card.model_dump_json(indent=2) + "\n"


def _check_warnings(card: ProductCard) -> str:
    if not card.check_warnings:
        return ""
    lines = [WARNINGS_INTRO, ""]
    lines += [f"- {warning.message}" for warning in card.check_warnings]
    return "\n".join(f"> {line}".rstrip() for line in lines)


def _seo(card: ProductCard) -> str:
    return "\n\n".join(
        [
            _section(TITLE_HEADING, card.seo_title),
            _section(DESCRIPTION_HEADING, card.seo_description),
        ]
    )


def _specs_table(card: ProductCard) -> str:
    rows = [
        f"| {_table_cell(spec.name)} | {_table_cell(spec.value)} |"
        for spec in card.specs
    ]
    return _section(
        "Ключевые характеристики",
        "\n".join(["| Характеристика | Значение |", "| --- | --- |", *rows]),
    )


def _commercial(card: ProductCard) -> str:
    commercial = card.commercial
    parts = [
        _section("Кому подходит", _bullets(commercial.audience), level=3),
        _section("Какие задачи решает", _bullets(commercial.tasks), level=3),
        _section("Как предложить клиенту", commercial.pitch, level=3),
    ]
    return _section("Для менеджера", "\n\n".join(parts))


def _section(heading: str, body: str, *, level: int = 2) -> str:
    return f"{'#' * level} {heading}\n\n{body}"


def _text_section(heading: str, body: str) -> str:
    return f"{heading.upper()}\n{body}"


def _bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
