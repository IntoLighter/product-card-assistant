import pytest

from app.core.checks import check_draft
from app.core.models import Commercial
from app.core.validation import normalize_product
from tests.factories import GOOD_DESCRIPTION, make_draft, manometer


def check(draft, raw=None):
    return check_draft(draft, normalize_product(raw or manometer()).product)


def fields(issues):
    return [issue.field for issue in issues]


def test_good_draft_passes():
    assert 800 <= len(GOOD_DESCRIPTION) <= 1200
    assert check(make_draft()) == []


def test_title_too_long():
    assert fields(check(make_draft(seo_title="М" * 71))) == ["seo_title"]


@pytest.mark.parametrize(
    ("description", "advice"),
    [("Коротко.", "Добавь ещё 8 предложений"), ("Д" * 1300, "Убери 2 предложения")],
)
def test_description_length_advice_in_sentences(description, advice):
    issues = check(make_draft(seo_description=description))
    assert fields(issues) == ["seo_description"]
    assert advice in issues[0].message


def test_empty_queries_not_counted():
    assert fields(check(make_draft(search_queries=["манометр", " ", ""]))) == ["search_queries"]


def test_incomplete_commercial():
    commercial = Commercial(audience=["службы КИПиА"], tasks=["контроль давления"], pitch=" ")
    assert fields(check(make_draft(commercial=commercial))) == ["commercial"]


def test_invented_number_detected_with_context():
    issues = check(make_draft(seo_description=GOOD_DESCRIPTION + " Рабочая температура до 150 °C."))
    assert fields(issues) == ["facts"]
    assert "«150» в «…Рабочая температура до 150 °C.»" in issues[0].message


def test_number_split_in_query_is_reported_with_query():
    issues = check(make_draft(search_queries=["манометр dm 02", "манометр манотомь", "манометр 1 6 мпа"]))
    assert "«6» в «манометр 1 6 мпа»" in issues[0].message


def test_verb_guarantee_is_not_a_warranty():
    assert check(make_draft(seo_description=GOOD_DESCRIPTION + " Прибор гарантирует наглядность.")) == []
    issues = check(make_draft(seo_description=GOOD_DESCRIPTION + " Гарантия 2 года."))
    assert "гарантия" in " ".join(issue.message for issue in issues)


def test_number_formats_are_equivalent():
    # «1.6» в тексте при «1,6» во входе — не выдумка
    assert check(make_draft(seo_title="Манометр DM 02 на 1.6 МПа")) == []


def test_risky_terms_detected():
    issues = check(make_draft(seo_description=GOOD_DESCRIPTION + " Соответствует ГОСТ и ТУ, корпус IP65."))
    message = " ".join(issue.message for issue in issues if issue.field == "facts")
    assert "ГОСТ" in message
    assert "ТУ" in message
    assert "IP" in message


def test_pronoun_tu_is_not_a_standard():
    assert check(make_draft(seo_description=GOOD_DESCRIPTION + " Прибор выполняет ту же задачу.")) == []


def test_risky_term_allowed_when_in_input():
    raw = manometer()
    raw["specs"]["степень защиты"] = "IP65"
    assert check(make_draft(seo_description=GOOD_DESCRIPTION + " Степень защиты IP65."), raw) == []
