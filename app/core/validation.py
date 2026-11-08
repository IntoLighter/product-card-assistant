"""
Разбор и нормализация входных данных.

Если карточку собрать нельзя (некорректный JSON, нет названия или обязательных
для категории характеристик), бросается InputError с понятным текстом. Прочие
пробелы в данных ошибкой не считаются: они возвращаются списком и попадают
в карточку как «требует уточнения».
"""

import re
from dataclasses import dataclass

from pydantic import ValidationError

from core.models import ProductInput, RawProduct
from core.templates import detect_template


class InputError(Exception):
    """Входные данные нельзя обработать."""


@dataclass(frozen=True)
class ParsedProduct:
    """Нормализованный товар и всё, что о входе стоит сообщить пользователю."""

    product: ProductInput
    empty_fields: list[str]
    ignored_fields: list[str]


def parse_json(text: str) -> RawProduct:
    """Текст JSON с одним товаром -> RawProduct."""
    if not text.strip():
        raise InputError("Пустой ввод: вставьте JSON с данными о товаре.")
    try:
        return RawProduct.model_validate_json(text)
    except ValidationError as error:
        raise InputError(_describe(error)) from error


def normalize_product(raw: RawProduct) -> ParsedProduct:
    """Товар из входа -> нормализованные данные и список пустых полей."""
    if not raw.name:
        raise InputError("Не заполнено обязательное поле «name» (название товара).")

    specs, empty_specs = _split_specs(raw.specs)

    empty_fields = []

    if not raw.manufacturer:
        empty_fields.append("Производитель")

    if not raw.description:
        empty_fields.append("Описание")

    empty_fields.extend(empty_specs)

    return ParsedProduct(
        product=ProductInput(
            name=raw.name,
            manufacturer=raw.manufacturer,
            specs=specs,
            description=raw.description,
        ),
        empty_fields=empty_fields,
        ignored_fields=sorted(raw.model_extra or {}),
    )


def ensure_required_specs(product: ProductInput) -> None:
    """InputError, если не заполнены обязательные по шаблону характеристики."""
    template = detect_template(product)
    missing = template.find_missing_required(product)
    if missing:
        raise InputError(
            f"Для категории «{template.category}» заполните "
            f"обязательные характеристики: {', '.join(missing)}."
        )


def _split_specs(raw_specs: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Характеристики с непустыми значениями и названия характеристик с пустыми."""
    if not raw_specs:
        return {}, ["Характеристики"]

    specs: dict[str, str] = {}
    empty: list[str] = []
    for name, value in raw_specs.items():
        if not name:
            continue
        if not value:
            empty.append(name)
        else:
            specs[name] = value
    return specs, empty


def _describe(error: ValidationError) -> str:
    """Первая ошибка разбора понятным пользователю текстом."""
    first = error.errors()[0]
    match first["type"], first["loc"]:
        case "json_invalid", _:
            reason = re.sub(
                r" at line (\d+) column (\d+)$",
                r" (строка \1, столбец \2)",
                first["ctx"]["error"],
            )
            return f"Некорректный JSON: {reason}."
        case "model_type", ():
            return "JSON должен быть объектом {...} с данными одного товара."
        case "dict_type", ("specs",):
            return (
                'Поле «specs» должно быть объектом вида {"характеристика": "значение"}.'
            )
        case "string_type", loc:
            where = ".".join(str(part) for part in loc)
            return f"Поле «{where}» должно быть строкой."
        case _, loc:
            where = ".".join(str(part) for part in loc)
            return f"Поле «{where}»: {first['msg']}."
