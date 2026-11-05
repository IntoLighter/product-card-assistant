import pytest

from app.core.profiles import detect_profile, find_missing
from app.core.validation import InputError, normalize_product, parse_json
from tests.factories import manometer


def test_invalid_json_reports_position():
    with pytest.raises(InputError, match="строка 1"):
        parse_json('{"name": "x",}')


@pytest.mark.parametrize("text", ["", "   ", "[]"])
def test_empty_input_rejected(text):
    with pytest.raises(InputError):
        parse_json(text)


@pytest.mark.parametrize("text", ['["строка"]', "42"])
def test_non_object_rejected(text):
    with pytest.raises(InputError, match="объектом"):
        parse_json(text)


def test_array_of_products():
    assert len(parse_json('[{"name": "a"}, {"name": "b"}]')) == 2


@pytest.mark.parametrize("name", [None, "", "   "])
def test_name_required(name):
    with pytest.raises(InputError, match="name"):
        normalize_product({"name": name})


def test_complete_product_has_no_gaps():
    parsed = normalize_product(manometer())
    assert parsed.gaps == []
    assert parsed.ignored_fields == []
    assert parsed.product.specs["класс точности"] == "1,5"


def test_empty_values_become_gaps():
    parsed = normalize_product(
        {
            "name": "  Термометр ТБ-63 ",
            "manufacturer": "",
            "description": None,
            "specs": {"диапазон измерений": "0…120 °C", "класс точности": None, "длина": "  "},
            "price": 100,
        }
    )
    assert parsed.product.name == "Термометр ТБ-63"
    assert parsed.product.manufacturer is None
    assert parsed.product.specs == {"диапазон измерений": "0…120 °C"}
    assert {gap.field for gap in parsed.gaps} == {
        "manufacturer",
        "description",
        "specs.класс точности",
        "specs.длина",
    }
    assert parsed.ignored_fields == ["price"]


def test_missing_specs_is_a_gap():
    parsed = normalize_product({"name": "Манометр"})
    assert "specs" in {gap.field for gap in parsed.gaps}


def test_specs_must_be_object():
    with pytest.raises(InputError, match="specs"):
        normalize_product({"name": "x", "specs": "0–1,6 МПа"})


def test_non_string_spec_values_are_converted():
    parsed = normalize_product({"name": "x", "specs": {"класс точности": 1.5, "среда": ["вода", "", "пар"]}})
    assert parsed.product.specs == {"класс точности": "1.5", "среда": "вода, пар"}


def test_profile_and_missing_fields():
    product = normalize_product(manometer()).product
    profile = detect_profile(product)
    assert profile.title.startswith("Манометр")
    missing = find_missing(product, profile)
    assert "Диапазон измерений" not in missing
    assert "Измеряемая среда" in missing


def test_unknown_category_uses_default_profile():
    product = normalize_product({"name": "Анализатор газа АГ-1"}).product
    assert detect_profile(product).title == "Контрольно-измерительный прибор"


def test_alias_matches_only_at_word_start():
    # «ду» (Ду, условный проход) не должно находиться внутри «градуировка»
    product = normalize_product({"name": "Расходомер Р-1", "specs": {"градуировка": "есть"}}).product
    assert "Диаметр условного прохода (DN)" in find_missing(product, detect_profile(product))
    product = normalize_product({"name": "Расходомер Р-1", "specs": {"Ду": "50"}}).product
    assert "Диаметр условного прохода (DN)" not in find_missing(product, detect_profile(product))
