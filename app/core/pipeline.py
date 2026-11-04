"""Сборка карточки: вход -> характеристики (кодом) -> LLM -> проверка -> исправление."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from .llm import LLMClient, LLMError, LLMOutputError
from .postcheck import check_draft
from .profiles import detect_profile, find_missing
from .prompts import build_fix_prompt, build_messages
from .schema import LLM_DRAFT_SCHEMA, MISSING, Issue, LLMDraft, ProductCard, ProductInput, SpecRow
from .validation import normalize_product

log = logging.getLogger(__name__)


def build_specs(product: ProductInput, missing: list[str]) -> list[SpecRow]:
    """Таблица характеристик собирается из входа КОДОМ — модель в неё не пишет,
    поэтому выдумать значение здесь невозможно."""
    rows = [SpecRow(name="Производитель", value=product.manufacturer or MISSING,
                    source="input" if product.manufacturer else "missing")]
    rows += [SpecRow(name=k, value=v, source="input") for k, v in product.specs.items()]
    rows += [SpecRow(name=m, value=MISSING, source="missing") for m in missing]
    return rows


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        key = item.strip().lower().rstrip(".")
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def generate_card(raw: dict, llm: LLMClient, max_attempts: int = 3, model_name: str = "") -> ProductCard:
    """Raises InputError (плохой вход) или LLMError (сбой LLM)."""
    product, input_issues = normalize_product(raw)
    profile = detect_profile(product)
    missing = find_missing(product, profile)
    base_messages = build_messages(product, profile, missing)

    messages = base_messages
    best: tuple[LLMDraft, list[Issue]] | None = None
    attempts = 0
    for attempt in range(max_attempts):
        attempts = attempt + 1
        try:
            data, raw_text = llm.complete_json(messages, LLM_DRAFT_SCHEMA, attempt=attempt)
            draft = LLMDraft.model_validate(data)
        except (LLMOutputError, ValidationError) as e:
            log.warning("Попытка %d: невалидный ответ модели: %s", attempts, e)
            messages = base_messages
            continue

        problems = check_draft(draft, product)
        log.info("Попытка %d: замечаний %d", attempts, len(problems))
        if best is None or len(problems) < len(best[1]):
            best = (draft, problems)
        if not problems:
            break
        # Повтор: исходный запрос + последний ответ + конкретные замечания проверки
        messages = base_messages + [
            {"role": "assistant", "content": raw_text},
            {"role": "user", "content": build_fix_prompt([p.message for p in problems])},
        ]

    if best is None:
        raise LLMError(f"Модель не вернула корректный ответ за {attempts} попыт(ки). Попробуйте ещё раз.")
    draft, problems = best

    clarifications = [f"{m}: {MISSING}" for m in missing]
    clarifications += [i.message for i in input_issues if i.level == "warning"]
    clarifications += draft.clarifications

    return ProductCard(
        product_name=product.name,
        manufacturer=product.manufacturer or MISSING,
        category=profile.title,
        seo_title=draft.seo_title.strip(),
        seo_description=draft.seo_description.strip(),
        specs=build_specs(product, missing),
        search_queries=[q.strip() for q in draft.search_queries if q.strip()],
        commercial=draft.commercial,
        needs_clarification=_dedupe(clarifications),
        # Замечания проверки, которые не удалось исправить, — показываем менеджеру
        issues=input_issues + [Issue(level="warning", field=p.field, message=p.message) for p in problems],
        meta={
            "model": model_name,
            "attempts": attempts,
            "seo_title_length": len(draft.seo_title.strip()),
            "seo_description_length": len(draft.seo_description.strip()),
            "checks_passed": not problems,
        },
    )
