"""Разбор и проверка входных данных. Ошибки — понятным языком, без трейсбеков."""

from __future__ import annotations

import json
from typing import Any

from .schema import Issue, ProductInput

KNOWN_FIELDS = {"name", "manufacturer", "specs", "description"}


class InputError(Exception):
    """Вход нельзя обработать (некорректный JSON, нет названия и т.п.)."""


def parse_json(text: str) -> list[dict]:
    """Строка -> список товаров. Принимает один объект или массив объектов."""
    if not text or not text.strip():
        raise InputError("Пустой ввод: вставьте JSON с данными о товаре.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise InputError(f"Некорректный JSON: {e.msg} (строка {e.lineno}, столбец {e.colno}).") from e

    items = data if isinstance(data, list) else [data]
    if not items:
        raise InputError("Пустой массив: нет ни одного товара.")
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            where = f"Элемент №{i}" if isinstance(data, list) else "Корень JSON"
            raise InputError(f"{where} должен быть объектом {{...}}, а не {type(item).__name__}.")
    return items


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v).strip() for v in value if str(v).strip())
    text = str(value).strip()
    return text or None


def normalize_product(raw: dict) -> tuple[ProductInput, list[Issue]]:
    """Сырой dict -> ProductInput + замечания о неполных данных."""
    if not isinstance(raw, dict):
        raise InputError("Данные о товаре должны быть JSON-объектом.")
    issues: list[Issue] = []

    name = _clean_str(raw.get("name"))
    if not name:
        raise InputError("Не заполнено обязательное поле «name» (название товара).")

    manufacturer = _clean_str(raw.get("manufacturer"))
    if not manufacturer:
        issues.append(Issue(level="warning", field="manufacturer", message="Не указан производитель."))

    description = _clean_str(raw.get("description"))
    if not description:
        issues.append(Issue(level="warning", field="description",
                            message="Нет текстового описания — текст будет построен только на характеристиках."))

    specs_raw = raw.get("specs")
    specs: dict[str, str] = {}
    if specs_raw is None or specs_raw == {}:
        issues.append(Issue(level="warning", field="specs", message="Не переданы характеристики (specs)."))
    elif not isinstance(specs_raw, dict):
        raise InputError("Поле «specs» должно быть объектом вида {\"характеристика\": \"значение\"}.")
    else:
        for key, value in specs_raw.items():
            key_clean = _clean_str(key)
            if not key_clean:
                continue
            if isinstance(value, dict):
                value = "; ".join(f"{k}: {v}" for k, v in value.items())
            value_clean = _clean_str(value)
            if value_clean is None:
                issues.append(Issue(level="warning", field=f"specs.{key_clean}",
                                    message=f"Пустое значение характеристики «{key_clean}»."))
                continue
            specs[key_clean] = value_clean

    for key in raw.keys() - KNOWN_FIELDS:
        issues.append(Issue(level="info", field=str(key), message=f"Поле «{key}» не используется и проигнорировано."))

    return ProductInput(name=name, manufacturer=manufacturer, specs=specs, description=description), issues
