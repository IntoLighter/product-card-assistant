import pytest
from conftest import make_draft

from app.core.llm import LLMError, LLMOutputError
from app.core.pipeline import generate_card
from app.core.render import to_markdown
from app.core.schema import MISSING


class FakeLLM:
    """Отдаёт заготовленные ответы по очереди и запоминает запросы."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def complete_json(self, messages, schema, attempt=0):
        self.calls.append(messages)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item.model_dump(), item.model_dump_json()


def test_happy_path(manometer):
    llm = FakeLLM(make_draft())
    card = generate_card(manometer, llm)
    assert card.meta["checks_passed"] and card.meta["attempts"] == 1
    # Характеристики — из входа, без участия модели
    values = {s.name: s.value for s in card.specs}
    assert values["класс точности"] == "1,5"
    assert values["Производитель"] == "Манотомь"
    assert "## Ключевые характеристики" in to_markdown(card)


def test_missing_specs_marked(manometer):
    card = generate_card(manometer, FakeLLM(make_draft()))
    missing = [s for s in card.specs if s.source == "missing"]
    assert missing and all(s.value == MISSING for s in missing)
    assert any("Измеряемая среда" in c for c in card.needs_clarification)


def test_retry_with_feedback(manometer):
    llm = FakeLLM(make_draft(seo_description="Слишком коротко."), make_draft())
    card = generate_card(manometer, llm)
    assert card.meta["attempts"] == 2 and card.meta["checks_passed"]
    fix_message = llm.calls[1][-1]["content"]
    assert "SEO-описание" in fix_message  # модели передали конкретное замечание


def test_unfixed_problems_shown_to_manager(manometer):
    bad = make_draft(seo_title="М" * 80)
    card = generate_card(manometer, FakeLLM(bad, bad, bad))
    assert not card.meta["checks_passed"]
    assert any(i.field == "seo_title" for i in card.issues)


def test_invalid_output_retried(manometer):
    card = generate_card(manometer, FakeLLM(LLMOutputError("не JSON"), make_draft()))
    assert card.meta["attempts"] == 2


def test_all_attempts_invalid(manometer):
    llm = FakeLLM(*[LLMOutputError("не JSON")] * 3)
    with pytest.raises(LLMError):
        generate_card(manometer, llm)


def test_connection_error_not_retried(manometer):
    llm = FakeLLM(LLMError("нет связи"), make_draft())
    with pytest.raises(LLMError, match="нет связи"):
        generate_card(manometer, llm)
    assert len(llm.calls) == 1
