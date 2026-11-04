from conftest import GOOD_DESCRIPTION, make_draft

from app.core.postcheck import check_draft
from app.core.validation import normalize_product


def _product(raw):
    return normalize_product(raw)[0]


def test_good_draft_passes(manometer):
    assert 800 <= len(GOOD_DESCRIPTION) <= 1200
    assert check_draft(make_draft(), _product(manometer)) == []


def test_title_too_long(manometer):
    issues = check_draft(make_draft(seo_title="М" * 71), _product(manometer))
    assert [i.field for i in issues] == ["seo_title"]


def test_description_too_short(manometer):
    issues = check_draft(make_draft(seo_description="Коротко."), _product(manometer))
    assert any(i.field == "seo_description" and "Добавь" in i.message for i in issues)


def test_invented_number_detected(manometer):
    draft = make_draft(seo_description=GOOD_DESCRIPTION + " Рабочая температура до 150 °C.")
    issues = check_draft(draft, _product(manometer))
    assert any(i.field == "facts" and "150" in i.message for i in issues)


def test_number_formats_are_equivalent(manometer):
    # «1.6» в тексте при «1,6» во входе — не выдумка
    draft = make_draft(seo_title="Манометр DM 02 на 1.6 МПа")
    assert check_draft(draft, _product(manometer)) == []


def test_risky_terms_detected(manometer):
    draft = make_draft(seo_description=GOOD_DESCRIPTION + " Соответствует ГОСТ, корпус IP65.")
    issues = check_draft(draft, _product(manometer))
    msg = " ".join(i.message for i in issues if i.field == "facts")
    assert "ГОСТ" in msg and "IP" in msg


def test_risky_term_allowed_when_in_input(manometer):
    manometer["specs"]["степень защиты"] = "IP65"
    draft = make_draft(seo_description=GOOD_DESCRIPTION + " Степень защиты IP65.")
    assert check_draft(draft, _product(manometer)) == []


def test_query_count(manometer):
    issues = check_draft(make_draft(search_queries=["a", "b"]), _product(manometer))
    assert any(i.field == "search_queries" for i in issues)
