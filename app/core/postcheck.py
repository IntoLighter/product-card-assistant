"""Проверка ответа модели кодом, а не «на честном слове» промпта.

1. Формат: длина заголовка/описания, число запросов, пустые поля.
2. Выдуманные факты: каждое число в текстах должно встречаться во входных данных;
   «рискованные» термины (ГОСТ, IP, взрывозащита, поверка...) — только если есть во входе.
"""

from __future__ import annotations

import re

from .schema import (
    DESCRIPTION_MAX,
    DESCRIPTION_MIN,
    QUERIES_MAX,
    QUERIES_MIN,
    TITLE_MAX,
    Issue,
    LLMDraft,
    ProductInput,
)

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

# (регулярка, как назвать в замечании). Срабатывает, если есть в ответе, но нет во входе.
RISKY_TERMS: tuple[tuple[str, str], ...] = (
    (r"гост", "ГОСТ"),
    (r"(?<!\w)ту(?!\w)", "ТУ"),
    (r"(?<![a-zа-я])ip\s?-?\d", "степень защиты IP"),
    (r"взрыво", "взрывозащита"),
    (r"(?<![a-zа-я])ex(?![a-zа-я])", "Ex-исполнение"),
    (r"госреестр|реестр си", "Госреестр СИ"),
    (r"сертифи", "сертификация"),
    (r"гаранти", "гарантия"),
    (r"поверк|поверен", "поверка"),
    (r"rs-?485|modbus|hart", "цифровой интерфейс"),
    (r"нержаве", "нержавеющая сталь"),
    (r"латун", "латунь"),
)


def _numbers(text: str) -> dict[float, str]:
    """{значение: как записано}. «1,6» и «1.6» — одно и то же число."""
    found: dict[float, str] = {}
    for m in NUMBER_RE.finditer(text):
        try:
            found.setdefault(float(m.group().replace(",", ".")), m.group())
        except ValueError:
            pass
    return found


def source_text(product: ProductInput) -> str:
    parts = [product.name, product.manufacturer or "", product.description or ""]
    for k, v in product.specs.items():
        parts += [k, v]
    return "\n".join(parts)


def draft_text(draft: LLMDraft) -> str:
    c = draft.commercial
    return "\n".join([draft.seo_title, draft.seo_description, *draft.search_queries,
                      *c.audience, *c.tasks, c.pitch])


def check_draft(draft: LLMDraft, product: ProductInput) -> list[Issue]:
    """Замечания к ответу. level=error — нарушение требований, повод перегенерировать."""
    issues: list[Issue] = []

    title_len = len(draft.seo_title.strip())
    if not title_len:
        issues.append(Issue(level="error", field="seo_title", message="SEO-заголовок пустой."))
    elif title_len > TITLE_MAX:
        issues.append(Issue(level="error", field="seo_title",
                            message=f"SEO-заголовок {title_len} символов, нужно не более {TITLE_MAX}. "
                                    f"Сократи на {title_len - TITLE_MAX}+."))

    desc_len = len(draft.seo_description.strip())
    if desc_len < DESCRIPTION_MIN:
        issues.append(Issue(level="error", field="seo_description",
                            message=f"SEO-описание {desc_len} символов, нужно {DESCRIPTION_MIN}–{DESCRIPTION_MAX}. "
                                    f"Добавь примерно {1000 - desc_len} символов, подробнее раскрыв назначение "
                                    f"и характеристики из данных."))
    elif desc_len > DESCRIPTION_MAX:
        issues.append(Issue(level="error", field="seo_description",
                            message=f"SEO-описание {desc_len} символов, нужно {DESCRIPTION_MIN}–{DESCRIPTION_MAX}. "
                                    f"Сократи примерно на {desc_len - 1000} символов."))

    queries = [q for q in draft.search_queries if q.strip()]
    if not QUERIES_MIN <= len(queries) <= QUERIES_MAX:
        issues.append(Issue(level="error", field="search_queries",
                            message=f"Поисковых запросов {len(queries)}, нужно {QUERIES_MIN}–{QUERIES_MAX}."))

    c = draft.commercial
    if not c.pitch.strip() or not any(a.strip() for a in c.audience) or not any(t.strip() for t in c.tasks):
        issues.append(Issue(level="error", field="commercial", message="Commercial-блок заполнен не полностью."))

    # --- выдуманные факты ---
    src = source_text(product)
    src_numbers = _numbers(src)
    out = draft_text(draft)
    invented = [raw for value, raw in _numbers(out).items() if value not in src_numbers]
    if invented:
        issues.append(Issue(level="error", field="facts",
                            message="В тексте есть числа, которых нет во входных данных: "
                                    + ", ".join(f"«{n}»" for n in invented) + ". Убери их."))

    src_low, out_low = src.lower(), out.lower()
    terms = [label for pattern, label in RISKY_TERMS
             if re.search(pattern, out_low) and not re.search(pattern, src_low)]
    if terms:
        issues.append(Issue(level="error", field="facts",
                            message="В тексте упомянуто то, чего нет во входных данных: "
                                    + ", ".join(terms) + ". Убери эти упоминания."))
    return issues
