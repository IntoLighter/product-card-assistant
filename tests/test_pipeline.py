import pytest

from core.llm import LLMError, LLMOutputError
from core.models import MISSING
from core.pipeline import generate_card
from core.validation import InputError
from factories import FakeLLM, make_draft, manometer, manometer_data, raw_product


def test_card_combines_input_and_draft():
    card = generate_card(manometer(), FakeLLM(make_draft()))

    assert card.meta.checks_passed
    assert card.meta.attempts == 1
    assert card.meta.llm_model == "fake-llm"
    assert card.seo_title == make_draft().seo_title
    # Характеристики — из входа, без участия модели
    values = {spec.name: spec.value for spec in card.specs}
    assert values["Производитель"] == "Манотомь"
    assert values["класс точности"] == "1,5"


def test_missing_specs_marked():
    card = generate_card(manometer(), FakeLLM(make_draft()))

    missing = [spec for spec in card.specs if spec.is_missing]
    assert [spec.name for spec in missing] == [
        "Измеряемая среда",
        "Температура рабочей среды",
    ]
    assert all(spec.value == MISSING for spec in missing)
    assert card.needs_clarification == ["Измеряемая среда", "Температура рабочей среды"]


def test_clarifications_list_empty_and_missing_fields_once():
    raw = manometer_data()
    raw["manufacturer"] = ""
    raw["specs"]["измеряемая среда"] = (
        ""  # пустая во входе и недостающая рекомендуемая одновременно
    )
    raw["warehouse"] = "Москва"

    card = generate_card(raw_product(raw), FakeLLM(make_draft()))

    assert card.manufacturer == MISSING
    assert card.specs[0].is_missing
    assert card.needs_clarification == [
        "Производитель",
        "измеряемая среда",
        "Температура рабочей среды",
    ]
    assert card.ignored_fields == ["warehouse"]


def test_missing_required_specs_stop_before_llm():
    raw = manometer_data()
    del raw["specs"]["класс точности"]
    llm = FakeLLM(make_draft())

    with pytest.raises(InputError, match="Класс точности"):
        generate_card(raw_product(raw), llm)
    assert llm.calls == []


def test_retry_sends_check_feedback():
    llm = FakeLLM(make_draft(seo_description="Слишком коротко."), make_draft())

    card = generate_card(manometer(), llm)

    assert card.meta.attempts == 2
    assert card.meta.checks_passed
    assert llm.attempts == [0, 1]  # seed сдвигается между попытками
    retry = llm.calls[1]
    assert retry[-2]["role"] == "assistant"
    assert "SEO-описание" in str(retry[-1]["content"])


def test_best_draft_kept_when_problems_remain():
    one_problem = make_draft(seo_title="М" * 80)
    two_problems = make_draft(seo_title="М" * 80, seo_description="Коротко.")

    card = generate_card(manometer(), FakeLLM(one_problem, two_problems, two_problems))

    assert card.meta.attempts == 3
    assert not card.meta.checks_passed
    assert [warning.field for warning in card.check_warnings] == ["seo_title"]


def test_invalid_output_is_retried():
    card = generate_card(manometer(), FakeLLM(LLMOutputError("не JSON"), make_draft()))
    assert card.meta.attempts == 2


def test_all_attempts_invalid():
    llm = FakeLLM(*[LLMOutputError("не JSON")] * 3)
    with pytest.raises(LLMError, match="3 попыток"):
        generate_card(manometer(), llm)


def test_connection_error_not_retried():
    llm = FakeLLM(LLMError("нет связи"), make_draft())
    with pytest.raises(LLMError, match="нет связи"):
        generate_card(manometer(), llm)
    assert len(llm.calls) == 1
