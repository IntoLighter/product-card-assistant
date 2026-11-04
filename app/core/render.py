"""Карточка -> Markdown / JSON для копирования контент-менеджером."""

from __future__ import annotations

from .schema import DESCRIPTION_MAX, DESCRIPTION_MIN, TITLE_MAX, ProductCard


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def to_markdown(card: ProductCard) -> str:
    m = card.meta
    lines = [f"# {card.product_name}", ""]

    warnings = [i for i in card.issues if i.level != "info"]
    if warnings:
        lines += ["> **Проверка нашла замечания — просмотрите перед публикацией:**"]
        lines += [f"> - {i.message}" for i in warnings]
        lines.append("")

    lines += [
        f"**Категория:** {card.category}  ",
        f"**Производитель:** {card.manufacturer}",
        "",
        f"## SEO-заголовок ({m.get('seo_title_length', len(card.seo_title))}/{TITLE_MAX} симв.)",
        "",
        card.seo_title,
        "",
        f"## SEO-описание ({m.get('seo_description_length', len(card.seo_description))} симв., "
        f"норма {DESCRIPTION_MIN}–{DESCRIPTION_MAX})",
        "",
        card.seo_description,
        "",
        "## Ключевые характеристики",
        "",
        "| Характеристика | Значение |",
        "|---|---|",
    ]
    lines += [f"| {_md_cell(s.name)} | {_md_cell(s.value)} |" for s in card.specs]
    lines += ["", "## Поисковые запросы", ""]
    lines += [f"- {q}" for q in card.search_queries]

    c = card.commercial
    lines += ["", "## Для менеджера", "", "**Кому подходит:**", ""]
    lines += [f"- {a}" for a in c.audience]
    lines += ["", "**Какие задачи решает:**", ""]
    lines += [f"- {t}" for t in c.tasks]
    lines += ["", f"**Как предложить клиенту:** {c.pitch}"]

    if card.needs_clarification:
        lines += ["", "## Требует уточнения", ""]
        lines += [f"- {x}" for x in card.needs_clarification]

    lines += ["", "---", f"_Черновик сгенерирован моделью {m.get('model') or '—'}, "
                         f"попыток: {m.get('attempts', '—')}. Технические значения взяты только из входных данных._"]
    return "\n".join(lines) + "\n"


def to_json(card: ProductCard) -> str:
    return card.model_dump_json(indent=2)
