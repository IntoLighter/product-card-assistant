"""
Разбор и нормализация входных данных.

Если карточку собрать нельзя (некорректный JSON, нет названия или обязательных
для категории характеристик), бросается InputError с понятным текстом. Прочие
пробелы в данных ошибкой не считаются: они возвращаются списком и попадают
в карточку как «требует уточнения».
"""

import json
from dataclasses import dataclass
from typing import Any

from core.models import ProductInput
from core.profiles import detect_profile, find_missing_required

KNOWN_FIELDS = frozenset({"name", "manufacturer", "specs", "description"})

type RawProduct = dict[str, Any]


class InputError(Exception):
    """Входные данные нельзя обработать."""


@dataclass(frozen=True)
class ParsedProduct:
    """Нормализованный товар и всё, что о входе стоит сообщить пользователю."""

    product: ProductInput
    # Названия полей, которые во входе пустые:
    # «Производитель», «Описание», «Класс точности»
    empty_fields: list[str]
    ignored_fields: list[str]


def parse_json(text: str) -> list[RawProduct]:
    """Текст JSON -> список товаров. Принимает один объект или массив объектов."""
    if not text.strip():
        raise InputError("Пустой ввод: вставьте JSON с данными о товаре.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise InputError(
            f"Некорректный JSON: {error.msg} "
            f"(строка {error.lineno}, столбец {error.colno})."
        ) from error

    items = data if isinstance(data, list) else [data]
    if not items:
        raise InputError("Пустой массив: нет ни одного товара.")
    for number, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            where = f"Элемент №{number}" if isinstance(data, list) else "Корень JSON"
            raise InputError(
                f"{where} должен быть объектом {{...}}, а не {type(item).__name__}."
            )
    return items


def normalize_product(raw: RawProduct) -> ParsedProduct:
    """Сырой объект товара -> нормализованные данные и список пустых полей."""
    name = _to_text(raw.get("name"))
    if name is None:
        raise InputError("Не заполнено обязательное поле «name» (название товара).")

    manufacturer = _to_text(raw.get("manufacturer"))
    description = _to_text(raw.get("description"))
    specs, empty_specs = _parse_specs(raw.get("specs"))
    empty_fields = [
        *(["Производитель"] if manufacturer is None else []),
        *(["Описание"] if description is None else []),
        *empty_specs,
    ]

    return ParsedProduct(
        product=ProductInput(
            name=name, manufacturer=manufacturer, specs=specs, description=description
        ),
        empty_fields=empty_fields,
        ignored_fields=sorted(raw.keys() - KNOWN_FIELDS),
    )


def ensure_required_specs(product: ProductInput) -> None:
    """InputError, если не заполнены обязательные для категории характеристики."""
    profile = detect_profile(product)
    missing = find_missing_required(product, profile)
    if missing:
        raise InputError(
            f"Для категории «{profile.title}» заполните обязательные характеристики: "
            f"{', '.join(missing)}."
        )


def _parse_specs(raw_specs: object) -> tuple[dict[str, str], list[str]]:
    """Характеристики с непустыми значениями и названия характеристик с пустыми."""
    if raw_specs is None or raw_specs == {}:
        return {}, ["Характеристики"]
    if not isinstance(raw_specs, dict):
        raise InputError(
            'Поле «specs» должно быть объектом вида {"характеристика": "значение"}.'
        )

    specs: dict[str, str] = {}
    empty: list[str] = []
    for raw_name, raw_value in raw_specs.items():
        name = _to_text(raw_name)
        if name is None:
            continue
        value = _to_text(raw_value)
        if value is None:
            empty.append(name)
        else:
            specs[name] = value
    return specs, empty


def _to_text(value: object) -> str | None:
    """Значение из JSON -> непустая строка без крайних пробелов или None."""
    if value is None:
        return None
    if isinstance(value, dict):
        text = "; ".join(f"{key}: {item}" for key, item in value.items())
    elif isinstance(value, list | tuple):
        text = ", ".join(part for item in value if (part := str(item).strip()))
    else:
        text = str(value)
    return text.strip() or None
