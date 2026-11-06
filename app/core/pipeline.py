"""
Сборка карточки товара.

    сырые данные -> нормализация -> категория и недостающие характеристики
        -> LLM (ответ по JSON-схеме) -> проверка -> исправление по замечаниям
        -> карточка

Таблицу характеристик собирает код из входных данных, модель в неё не пишет,
поэтому выдуманное значение в таблице появиться не может.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from openai.types.chat import ChatCompletionMessageParam

from core.checks import check_draft
from core.llm import LLMClient, LLMError, LLMOutputError
from core.models import (
    MISSING,
    CardMeta,
    Issue,
    LLMDraft,
    ProductCard,
    ProductInput,
    SpecRow,
)
from core.postprocess import fit_draft
from core.profiles import detect_profile, find_missing
from core.prompts import build_fix_messages, build_messages
from core.validation import RawProduct, ensure_required_specs, normalize_product

log = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class CheckedDraft:
    """Лучший из полученных ответов модели и замечания, которые к нему остались."""

    draft: LLMDraft
    problems: list[Issue]
    attempts: int


def generate_card(
    raw: RawProduct, llm: LLMClient, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS
) -> ProductCard:
    """
    Черновик карточки по сырым данным о товаре.

    Бросает InputError, если данные нельзя обработать, и LLMError,
    если LLM недоступна или ни разу не вернула корректный ответ.
    """
    parsed = normalize_product(raw)
    product = parsed.product
    ensure_required_specs(
        product
    )  # до обращения к LLM: без обязательных данных генерировать нечего
    profile = detect_profile(product)
    missing = find_missing(product, profile)

    result = generate_checked_draft(
        llm, product, build_messages(product, profile, missing), max_attempts
    )
    draft = result.draft
    return ProductCard(
        product_name=product.name,
        manufacturer=product.manufacturer or MISSING,
        category=profile.title,
        seo_title=draft.seo_title,
        seo_description=draft.seo_description,
        specs=build_specs(product, missing),
        search_queries=[query for query in draft.search_queries if query],
        commercial=draft.commercial,
        needs_clarification=_unique([*parsed.empty_fields, *missing]),
        check_warnings=result.problems,
        ignored_fields=parsed.ignored_fields,
        meta=CardMeta(
            llm_model=llm.model_name,
            attempts=result.attempts,
            seo_title_length=len(draft.seo_title),
            seo_description_length=len(draft.seo_description),
            checks_passed=not result.problems,
        ),
    )


def generate_checked_draft(
    llm: LLMClient,
    product: ProductInput,
    messages: list[ChatCompletionMessageParam],
    max_attempts: int,
) -> CheckedDraft:
    """
    Генерирует ответ и при замечаниях проверки просит модель его исправить.

    Возвращает лучший ответ (с наименьшим числом замечаний) из max_attempts попыток.
    """
    best: tuple[LLMDraft, list[Issue]] | None = None
    conversation = messages
    attempts = 0
    for attempt in range(max_attempts):
        attempts += 1
        try:
            draft = fit_draft(llm.generate(conversation, LLMDraft, attempt=attempt))
        except LLMOutputError as error:
            log.warning("Попытка %d: невалидный ответ модели (%s)", attempts, error)
            conversation = messages
            continue

        problems = check_draft(draft, product)
        log.info(
            "Попытка %d: замечаний проверки — %d %s",
            attempts,
            len(problems),
            [p.message for p in problems],
        )
        if best is None or len(problems) < len(best[1]):
            best = (draft, problems)
        if not problems:
            break
        conversation = build_fix_messages(messages, draft.model_dump_json(), problems)

    if best is None:
        raise LLMError(
            "Модель не вернула корректный ответ "
            f"ни в одной из {attempts} попыток. Попробуйте ещё раз."
        )
    draft, problems = best
    return CheckedDraft(draft=draft, problems=problems, attempts=attempts)


def build_specs(product: ProductInput, missing: list[str]) -> list[SpecRow]:
    """
    Таблица характеристик.

    Производитель, все характеристики из входа и недостающие с пометкой «данных нет».
    """
    return [
        SpecRow(
            name="Производитель",
            value=product.manufacturer or MISSING,
            is_missing=not product.manufacturer,
        ),
        *(SpecRow(name=name, value=value) for name, value in product.specs.items()),
        *(SpecRow(name=title, value=MISSING, is_missing=True) for title in missing),
    ]


def _unique(items: Iterable[str]) -> list[str]:
    """
    Без повторов (без учёта регистра), в исходном порядке.

    Пустое во входе поле («диаметр корпуса»: "") попадает и в пустые поля,
    и в недостающие рекомендуемые («Диаметр корпуса») — в списке оно должно быть одно.
    """
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item.strip())
    return unique
