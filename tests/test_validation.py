import pytest

from app.core.profiles import detect_profile, find_missing
from app.core.validation import InputError, normalize_product, parse_json


def test_invalid_json_reports_position():
    with pytest.raises(InputError, match="строка 1"):
        parse_json('{"name": "x",}')


@pytest.mark.parametrize("text", ["", "   ", "[]"])
def test_empty_input(text):
    with pytest.raises(InputError):
        parse_json(text)


def test_non_object_rejected():
    with pytest.raises(InputError, match="объектом"):
        parse_json('["строка"]')


def test_array_of_products():
    assert len(parse_json('[{"name": "a"}, {"name": "b"}]')) == 2


@pytest.mark.parametrize("name", [None, "", "   "])
def test_name_required(name):
    with pytest.raises(InputError, match="name"):
        normalize_product({"name": name})


def test_empty_fields_become_warnings():
    product, issues = normalize_product({
        "name": "Термометр ТБ-63", "manufacturer": "", "description": None,
        "specs": {"диапазон измерений": "0…120 °C", "класс точности": None, "длина": "  "},
        "price": 100,
    })
    assert product.manufacturer is None
    assert product.specs == {"диапазон измерений": "0…120 °C"}
    fields = {i.field for i in issues}
    assert {"manufacturer", "description", "specs.класс точности", "specs.длина", "price"} <= fields


def test_specs_must_be_object():
    with pytest.raises(InputError, match="specs"):
        normalize_product({"name": "x", "specs": "0–1,6 МПа"})


def test_numeric_spec_values_are_kept():
    product, _ = normalize_product({"name": "x", "specs": {"класс точности": 1.5}})
    assert product.specs["класс точности"] == "1.5"


def test_profile_and_missing_fields():
    product, _ = normalize_product({"name": "Манометр показывающий DM 02",
                                    "specs": {"диапазон измерений": "0–1,6 МПа", "класс точности": "1,5"}})
    profile = detect_profile(product)
    assert profile.title.startswith("Манометр")
    missing = find_missing(product, profile)
    assert "Диапазон измерений" not in missing
    assert "Присоединение" in missing


def test_word_start_matching():
    # «ду» не должно находиться внутри «градуировка»
    product, _ = normalize_product({"name": "Расходомер Р-1", "specs": {"градуировка": "есть"}})
    assert any("DN" in m for m in find_missing(product, detect_profile(product)))
