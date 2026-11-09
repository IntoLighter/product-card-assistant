"""Шаблоны приборов: формат файлов, выбор шаблона по названию, поиск недостающего."""

import pytest
from pydantic import ValidationError

from core.models import RawProduct
from core.resources import templates_dir
from core.templates import (
    OTHER_DEVICE_LABEL,
    ProductTemplate,
    detect_template,
    load_templates,
)
from core.validation import ensure_required_specs, normalize_product
from factories import raw_product

TEMPLATES = load_templates()


def product(name, specs=None):
    return normalize_product(raw_product({"name": name, "specs": specs or {}})).product


@pytest.mark.parametrize(
    "path", sorted(templates_dir().glob("*.json")), ids=lambda path: path.name
)
def test_template_file_format(path):
    # Лишние ключи, не-объект в required, нет category — ошибка
    template = ProductTemplate.model_validate_json(path.read_bytes())
    assert not template.required.keys() & template.recommended.keys(), (
        "характеристика и обязательная, и рекомендуемая"
    )


def test_invalid_template_rejected():
    with pytest.raises(ValidationError):  # нет category
        ProductTemplate.model_validate({"required": {"Класс точности": []}})
    with pytest.raises(ValidationError):  # старый формат: список вместо объекта
        ProductTemplate.model_validate(
            {"category": "Манометр", "required": ["Класс точности"]}
        )
    with pytest.raises(ValidationError):  # неизвестный ключ
        ProductTemplate.model_validate(
            {"category": "Манометр", "required": {"Класс точности": []}, "price": 1}
        )


def test_template_becomes_form_data_with_required_specs():
    template = ProductTemplate(
        name="Манометр",
        category="Манометр",
        required={"Диапазон измерений": ["диапазон"], "Класс точности": []},
        recommended={"Измеряемая среда": ["сред"]},
    )
    assert template.to_raw_product() == RawProduct(
        name="Манометр",
        specs={"Диапазон измерений": "", "Класс точности": ""},
    )


def test_other_device_is_last_and_only_default():
    assert TEMPLATES[-1].label == OTHER_DEVICE_LABEL
    assert [template.label for template in TEMPLATES if not template.keywords] == [
        OTHER_DEVICE_LABEL
    ]


@pytest.mark.parametrize(
    ("name", "category"),
    [
        ("Вакуумметр ВП-100", "Манометр (показывающий прибор давления)"),
        ("Датчик давления ПД-100", "Датчик (преобразователь) давления"),
        ("Термопреобразователь ТС-1", "Датчик температуры / термометр"),
        ("Счётчик воды СВ-15", "Расходомер / счётчик"),
        ("Анализатор газа АГ-1", "Контрольно-измерительный прибор"),
    ],
    ids=[
        "vacuum-gauge",
        "pressure-sensor",
        "temperature-sensor",
        "water-meter",
        "unknown",
    ],
)
def test_template_detected_by_keywords(name, category):
    assert detect_template(product(name)).category == category


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda template: template.label)
def test_filled_template_passes_required_check(template):
    # Форма из шаблона с вписанными значениями — достаточно для генерации
    name = template.name or "Прибор"
    filled = product(name, dict.fromkeys(template.required, "значение"))
    assert detect_template(filled) == template
    ensure_required_specs(filled)


def test_empty_template_blocks_generation():
    manometer = next(template for template in TEMPLATES if template.name == "Манометр")
    raw = manometer.to_raw_product().model_copy(update={"name": "Манометр ДМ-1"})
    filled = normalize_product(raw).product
    assert len(manometer.find_missing_required(filled)) == len(manometer.required)


def test_missing_lists_required_and_recommended():
    manometer = product(
        "Манометр ДМ-1",
        {"диапазон измерений": "0–1,6 МПа", "класс точности": "1,5"},
    )
    missing = detect_template(manometer).find_missing(manometer)
    assert "Диапазон измерений" not in missing
    assert "Присоединение" in missing  # обязательная
    assert "Измеряемая среда" in missing  # рекомендуемая


def test_spec_recognized_by_alias():
    sensor = product(
        "Датчик давления ПД-1",
        {"основная приведённая погрешность": "±0,5 %"},
    )
    assert "Класс точности" not in detect_template(sensor).find_missing(sensor)


def test_alias_matches_only_at_word_start():
    # «ду» (Ду, условный проход) не должно находиться внутри «градуировка»
    dn = "Диаметр условного прохода (DN)"
    flowmeter = product("Расходомер Р-1", {"градуировка": "есть"})
    assert dn in detect_template(flowmeter).find_missing(flowmeter)
    flowmeter = product("Расходомер Р-1", {"Ду": "50"})
    assert dn not in detect_template(flowmeter).find_missing(flowmeter)
