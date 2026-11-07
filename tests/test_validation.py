import pytest

from core.profiles import detect_profile, find_missing
from core.validation import (
    InputError,
    ensure_required_specs,
    normalize_product,
    parse_json,
)
from factories import manometer, manometer_data, raw_product


def test_invalid_json_reports_position():
    with pytest.raises(InputError, match="строка 1"):
        parse_json('{"name": "x",}')


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_input_rejected(text):
    with pytest.raises(InputError):
        parse_json(text)


@pytest.mark.parametrize("text", ['[{"name": "a"}]', '["строка"]', "42"])
def test_non_object_rejected(text):
    with pytest.raises(InputError, match="объектом"):
        parse_json(text)


def test_one_product_parsed():
    raw = parse_json('{"name": "Манометр", "specs": {"класс точности": "1,5"}}')
    assert raw.name == "Манометр"
    assert raw.specs == {"класс точности": "1,5"}


@pytest.mark.parametrize(
    "text", ['{"name": null}', '{"name": "x", "specs": {"класс точности": 1.5}}']
)
def test_non_string_values_rejected(text):
    with pytest.raises(InputError, match="строкой"):
        parse_json(text)


@pytest.mark.parametrize("name", ["", "   "])
def test_name_required(name):
    with pytest.raises(InputError, match="name"):
        normalize_product(raw_product({"name": name}))


def test_complete_product_has_no_empty_fields():
    parsed = normalize_product(manometer())
    assert parsed.empty_fields == []
    assert parsed.ignored_fields == []
    assert parsed.product.specs["класс точности"] == "1,5"


def test_empty_values_listed_by_name():
    parsed = normalize_product(
        raw_product(
            {
                "name": "  Термометр ТБ-63 ",
                "manufacturer": "",
                "description": "",
                "specs": {
                    "диапазон измерений": "0…120 °C",
                    "класс точности": "",
                    "длина": "  ",
                },
                "price": 100,
            }
        )
    )
    assert parsed.product.name == "Термометр ТБ-63"
    assert parsed.product.manufacturer is None
    assert parsed.product.specs == {"диапазон измерений": "0…120 °C"}
    assert parsed.empty_fields == [
        "Производитель",
        "Описание",
        "класс точности",
        "длина",
    ]
    assert parsed.ignored_fields == ["price"]


def test_missing_specs_listed_as_empty_field():
    parsed = normalize_product(raw_product({"name": "Манометр"}))
    assert "Характеристики" in parsed.empty_fields


def test_specs_must_be_object():
    with pytest.raises(InputError, match="specs"):
        parse_json('{"name": "x", "specs": "0–1,6 МПа"}')


def test_profile_and_missing_fields():
    product = normalize_product(manometer()).product
    profile = detect_profile(product)
    assert profile.title.startswith("Манометр")
    missing = find_missing(product, profile)
    assert "Диапазон измерений" not in missing
    assert "Измеряемая среда" in missing


def test_complete_manometer_passes_required_check():
    ensure_required_specs(normalize_product(manometer()).product)


def test_missing_required_spec_rejected():
    raw = manometer_data()
    del raw["specs"]["присоединение"]
    with pytest.raises(InputError, match=r"Манометр.*Присоединение"):
        ensure_required_specs(normalize_product(raw_product(raw)).product)


def test_required_error_lists_all_missing_specs():
    product = normalize_product(
        raw_product(
            {"name": "Датчик давления ПД-1", "specs": {"диапазон измерений": "0–1 МПа"}}
        )
    ).product
    with pytest.raises(InputError) as error:
        ensure_required_specs(product)
    message = str(error.value)
    for title in ["Класс точности", "Выходной сигнал", "Питание"]:
        assert title in message
    assert "Диапазон" not in message


def test_empty_required_value_counts_as_missing():
    # Пустой «класс точности» — то же, что отсутствие характеристики
    raw = raw_product(
        {
            "name": "Термометр ТБ-63",
            "specs": {"диапазон измерений": "0…120 °C", "класс точности": ""},
        }
    )
    with pytest.raises(InputError, match="Класс точности"):
        ensure_required_specs(normalize_product(raw).product)


def test_unknown_category_uses_default_profile():
    product = normalize_product(raw_product({"name": "Анализатор газа АГ-1"})).product
    assert detect_profile(product).title == "Контрольно-измерительный прибор"


def test_alias_matches_only_at_word_start():
    # «ду» (Ду, условный проход) не должно находиться внутри «градуировка»
    product = normalize_product(
        raw_product({"name": "Расходомер Р-1", "specs": {"градуировка": "есть"}})
    ).product
    assert "Диаметр условного прохода (DN)" in find_missing(
        product, detect_profile(product)
    )
    product = normalize_product(
        raw_product({"name": "Расходомер Р-1", "specs": {"Ду": "50"}})
    ).product
    assert "Диаметр условного прохода (DN)" not in find_missing(
        product, detect_profile(product)
    )
