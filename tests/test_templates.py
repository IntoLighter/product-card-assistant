"""Шаблоны формы должны совпадать с обязательными характеристиками профилей."""

import pytest
from pydantic import ValidationError

from core.profiles import (
    DEFAULT_PROFILE,
    PROFILES,
    detect_profile,
    find_missing_required,
)
from core.resources import templates_dir
from core.templates import OTHER_DEVICE_LABEL, ProductTemplate, load_templates
from core.validation import ensure_required_specs, normalize_product

TEMPLATES = load_templates()


def filled(raw):
    """Шаблон с вписанными значениями (у «Другого прибора» — и название)."""
    return {
        **raw,
        "name": raw["name"] or "Прибор",
        "specs": dict.fromkeys(raw["specs"], "значение"),
    }


@pytest.mark.parametrize(
    "path", sorted(templates_dir().glob("*.json")), ids=lambda path: path.name
)
def test_template_file_format(path):
    template = ProductTemplate.model_validate_json(
        path.read_bytes()
    )  # лишние ключи и не-список specs — ошибка
    assert len(set(template.specs)) == len(template.specs), (
        "характеристики в шаблоне повторяются"
    )


def test_template_becomes_form_data_with_empty_values():
    template = ProductTemplate(
        name="Манометр", specs=["Диапазон измерений", "Класс точности"]
    )
    assert template.to_raw_product() == {
        "name": "Манометр",
        "specs": {"Диапазон измерений": "", "Класс точности": ""},
    }


def test_invalid_template_rejected():
    with pytest.raises(ValidationError):
        ProductTemplate.model_validate(
            {"name": "Манометр", "specs": {"Класс точности": ""}}
        )
    with pytest.raises(ValidationError):
        ProductTemplate.model_validate(
            {"name": "Манометр", "specs": ["Класс точности"], "price": 100}
        )


def test_every_profile_has_exactly_one_template():
    covered = [
        detect_profile(normalize_product(filled(raw)).product)
        for raw in TEMPLATES.values()
    ]
    for profile in (*PROFILES, DEFAULT_PROFILE):
        assert covered.count(profile) == 1, profile.title


@pytest.mark.parametrize("label", list(TEMPLATES))
def test_template_contains_exactly_required_specs(label):
    product = normalize_product(filled(TEMPLATES[label])).product
    profile = detect_profile(product)

    assert find_missing_required(product, profile) == [], (
        "в шаблоне не хватает обязательных характеристик"
    )
    assert len(product.specs) == len(profile.required), (
        "в шаблоне есть лишние характеристики"
    )
    ensure_required_specs(product)


def test_empty_template_blocks_generation():
    product = normalize_product(
        {**TEMPLATES["Манометр"], "name": "Манометр ДМ-1"}
    ).product
    assert len(find_missing_required(product, detect_profile(product))) == 3


def test_other_device_is_last():
    assert list(TEMPLATES)[-1] == OTHER_DEVICE_LABEL
