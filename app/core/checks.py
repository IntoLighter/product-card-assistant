"""
Автоматическая проверка ответа модели.

Промпт просит модель не выдумывать, а эта проверка контролирует результат:

1. формат — длины текстов и число поисковых запросов из ТЗ;
2. факты — каждое число в текстах должно встречаться во входных данных,
   а «рискованные» сведения (ГОСТ, IP, поверка и т. п.) допустимы,
   только если они есть во входе.

Найденные проблемы отправляются модели на исправление,
а те, что остались, показываются контент-менеджеру.
"""

import re
from typing import NamedTuple

from core.models import (
    DESCRIPTION_MAX_LEN,
    DESCRIPTION_MIN_LEN,
    DESCRIPTION_TARGET_LEN,
    QUERIES_MAX,
    QUERIES_MIN,
    TITLE_MAX_LEN,
    Commercial,
    Issue,
    LLMDraft,
    ProductInput,
)

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Средняя длина предложения в описаниях (15–20 слов):
# чтобы пересчитать символы в предложения
CHARS_PER_SENTENCE = 120


class RiskyTerm(NamedTuple):
    label: str
    pattern: re.Pattern[str]


def _term(label: str, pattern: str, flags: re.RegexFlag = re.IGNORECASE) -> RiskyTerm:
    return RiskyTerm(label, re.compile(pattern, flags))


# Сведения, которые модели склонны «додумывать».
# Допустимы, только если есть во входных данных.
RISKY_TERMS: tuple[RiskyTerm, ...] = (
    _term("ГОСТ", r"гост"),
    # Регистр важен: «ту» — ещё и местоимение («выполняет ту же задачу»)
    _term("ТУ", r"(?<!\w)ТУ(?!\w)", flags=re.NOFLAG),
    _term("степень защиты IP", r"(?<![a-z])ip\s?-?\d"),
    _term("взрывозащита", r"взрыво"),
    _term(
        "Ex-исполнение", r"(?<![A-Za-zА-Яа-яЁё])Ex(?![A-Za-zА-Яа-яЁё])", flags=re.NOFLAG
    ),
    _term("Госреестр СИ", r"госреестр|реестр си"),
    _term("сертификация", r"сертифи"),
    # Только существительное: «гарантирует точность» — оборот речи,
    # а не обещание гарантии
    _term("гарантия", r"гаранти(?:я|и|ю|ей|йн)"),
    _term("поверка", r"поверк|поверен"),
    _term("цифровой интерфейс", r"rs-?485|modbus|hart"),
    _term("нержавеющая сталь", r"нержаве"),
    _term("латунь", r"латун"),
)


def check_draft(draft: LLMDraft, product: ProductInput) -> list[Issue]:
    """Все замечания к ответу модели; пустой список означает, что ответ годится."""
    return [
        *_check_title(draft.seo_title),
        *_check_description(draft.seo_description),
        *_check_queries(draft.search_queries),
        *_check_commercial(draft.commercial),
        *_check_facts(draft, product),
    ]


def _check_title(title: str) -> list[Issue]:
    length = len(title.strip())
    if length == 0:
        return [Issue(field="seo_title", message="SEO-заголовок пустой.")]
    if length > TITLE_MAX_LEN:
        excess = length - TITLE_MAX_LEN
        return [
            Issue(
                field="seo_title",
                message=f"SEO-заголовок {length} символов, "
                f"нужно не более {TITLE_MAX_LEN}. "
                f"Сократи его минимум на {excess} символов.",
            )
        ]
    return []


def _check_description(description: str) -> list[Issue]:
    # Символы модель считать не умеет, а предложения — умеет:
    # подсказку даём в предложениях
    length = len(description.strip())
    if length < DESCRIPTION_MIN_LEN:
        sentences = _sentences_for(DESCRIPTION_TARGET_LEN - length)
        advice = (
            f"Добавь ещё {sentences} по 15–20 слов: раскрой назначение, "
            "что дают характеристики из данных на практике и где применяется прибор. "
            "Новых чисел и свойств не добавляй."
        )
    elif length > DESCRIPTION_MAX_LEN:
        excess = _sentences_for(length - DESCRIPTION_TARGET_LEN)
        advice = f"Убери {excess}, остальное сохрани."
    else:
        return []
    norm = f"нужно {DESCRIPTION_MIN_LEN}–{DESCRIPTION_MAX_LEN}"
    return [
        Issue(
            field="seo_description",
            message=f"SEO-описание {length} символов, {norm}. {advice}",
        )
    ]


def _check_queries(queries: list[str]) -> list[Issue]:
    count = sum(1 for query in queries if query.strip())
    if QUERIES_MIN <= count <= QUERIES_MAX:
        return []
    return [
        Issue(
            field="search_queries",
            message=f"Непустых поисковых запросов {count}, "
            f"нужно {QUERIES_MIN}–{QUERIES_MAX}.",
        )
    ]


def _check_commercial(commercial: Commercial) -> list[Issue]:
    has_audience = any(item.strip() for item in commercial.audience)
    has_tasks = any(item.strip() for item in commercial.tasks)
    if has_audience and has_tasks and commercial.pitch.strip():
        return []
    return [
        Issue(
            field="commercial",
            message="Commercial-блок заполнен не полностью: "
            "нужны аудитория, задачи и короткий питч.",
        )
    ]


def _check_facts(draft: LLMDraft, product: ProductInput) -> list[Issue]:
    source, generated = _source_text(product), _generated_text(draft)
    issues: list[Issue] = []

    invented_numbers = _invented_numbers(generated, source)
    if invented_numbers:
        listed = "; ".join(invented_numbers)
        issues.append(
            Issue(
                field="facts",
                message="В тексте есть числа, которых нет во входных данных: "
                f"{listed}. "
                "Убери их или запиши точно так, как в данных.",
            )
        )

    invented_terms = [
        term.label
        for term in RISKY_TERMS
        if term.pattern.search(generated) and not term.pattern.search(source)
    ]
    if invented_terms:
        listed = ", ".join(invented_terms)
        issues.append(
            Issue(
                field="facts",
                message="В тексте упомянуто то, чего нет во входных данных: "
                f"{listed}. Убери эти упоминания.",
            )
        )
    return issues


def _sentences_for(chars: int) -> str:
    """Сколько предложений средней длины занимают chars символов: «3 предложения»."""
    count = max(1, round(chars / CHARS_PER_SENTENCE))
    last_digit, teens = count % 10, count % 100 // 10 == 1
    if last_digit == 1 and not teens:
        word = "предложение"
    elif last_digit in {2, 3, 4} and not teens:
        word = "предложения"
    else:
        word = "предложений"
    return f"{count} {word}"


def _invented_numbers(generated: str, source: str) -> list[str]:
    """
    Числа из текста модели, которых нет во входе, с местом, где они встретились.

    Контекст нужен модели при исправлении: «6» само по себе непонятно,
    а «6» в «манометр 1 6 мпа» — понятно.
    """
    allowed = {_number_value(match) for match in NUMBER.finditer(source)}
    invented: dict[float, str] = {}
    for match in NUMBER.finditer(generated):
        value = _number_value(match)
        if value not in allowed and value not in invented:
            invented[value] = f"«{match.group()}» в «{_context(generated, match)}»"
    return list(invented.values())


def _number_value(match: re.Match[str]) -> float:
    """«1,6» и «1.6» — одно и то же число."""
    return float(match.group().replace(",", "."))


def _context(text: str, match: re.Match[str], width: int = 25) -> str:
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    line_end = len(text) if line_end == -1 else line_end
    start, end = (
        max(line_start, match.start() - width),
        min(line_end, match.end() + width),
    )
    prefix = "…" if start > line_start else ""
    suffix = "…" if end < line_end else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def _source_text(product: ProductInput) -> str:
    spec_parts = [
        part for name, value in product.specs.items() for part in (name, value)
    ]
    return "\n".join(
        [
            product.name,
            product.manufacturer or "",
            product.description or "",
            *spec_parts,
        ]
    )


def _generated_text(draft: LLMDraft) -> str:
    commercial = draft.commercial
    return "\n".join(
        [
            draft.seo_title,
            draft.seo_description,
            *draft.search_queries,
            *commercial.audience,
            *commercial.tasks,
            commercial.pitch,
        ]
    )
