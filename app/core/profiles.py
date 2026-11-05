"""
Категории приборов и характеристики, которые ожидаются в их карточках.

Если ожидаемой характеристики нет во входных данных, карточка показывает её
со значением «данных нет», а модель получает указание не упоминать её в текстах.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import ProductInput


@dataclass(frozen=True)
class SpecField:
    """Ожидаемая характеристика и начала слов, по которым она узнаётся во входных данных."""

    title: str
    aliases: tuple[str, ...]

    def is_present(self, spec_names: Iterable[str]) -> bool:
        return any(_starts_word(alias, name) for name in spec_names for alias in self.aliases)


@dataclass(frozen=True)
class Profile:
    """Категория приборов: как узнать её по названию и какие характеристики ожидаются."""

    title: str
    name_keywords: tuple[str, ...]
    expected: tuple[SpecField, ...]

    def matches(self, product_name: str) -> bool:
        name = product_name.lower()
        return any(keyword in name for keyword in self.name_keywords)


MEASURING_RANGE = SpecField("Диапазон измерений", ("диапазон", "предел"))
ACCURACY = SpecField("Класс точности / погрешность", ("класс точности", "точност", "погрешност", "класс допуска"))
CONNECTION = SpecField("Присоединение", ("присоедин", "резьб", "штуцер"))
MEDIUM = SpecField("Измеряемая среда", ("сред",))
MEDIUM_TEMPERATURE = SpecField("Температура рабочей среды", ("температур",))
OUTPUT_SIGNAL = SpecField("Выходной сигнал / интерфейс", ("выход", "сигнал", "интерфейс", "rs-485", "modbus", "hart"))
POWER_SUPPLY = SpecField("Питание", ("питани", "напряжени"))
PROTECTION = SpecField("Степень защиты", ("ip", "степень защиты", "пылевлагозащ"))
CASE_DIAMETER = SpecField("Диаметр корпуса", ("диаметр",))
IMMERSION_LENGTH = SpecField("Длина погружной части", ("длина", "погружн"))
NOMINAL_DIAMETER = SpecField("Диаметр условного прохода (DN)", ("dn", "ду", "условного прохода", "номинальн"))

PROFILES: tuple[Profile, ...] = (
    Profile(
        title="Манометр (показывающий прибор давления)",
        name_keywords=("манометр", "вакуумметр", "мановакуумметр", "напоромер", "тягомер"),
        expected=(MEASURING_RANGE, ACCURACY, CONNECTION, CASE_DIAMETER, MEDIUM, MEDIUM_TEMPERATURE),
    ),
    Profile(
        title="Датчик (преобразователь) давления",
        name_keywords=("датчик давления", "преобразователь давления", "датчик избыточного", "датчик абсолютного"),
        expected=(MEASURING_RANGE, ACCURACY, OUTPUT_SIGNAL, POWER_SUPPLY, CONNECTION, PROTECTION, MEDIUM),
    ),
    Profile(
        title="Датчик температуры / термометр",
        name_keywords=("термометр", "термопреобразоват", "датчик температуры", "термопар", "термосопротивлен"),
        expected=(MEASURING_RANGE, ACCURACY, IMMERSION_LENGTH, CONNECTION, OUTPUT_SIGNAL),
    ),
    Profile(
        title="Расходомер / счётчик",
        name_keywords=("расходомер", "счётчик", "счетчик"),
        expected=(MEASURING_RANGE, ACCURACY, NOMINAL_DIAMETER, OUTPUT_SIGNAL, POWER_SUPPLY, PROTECTION),
    ),
    Profile(
        title="Уровнемер / сигнализатор уровня",
        name_keywords=("уровнемер", "сигнализатор уровня", "датчик уровня"),
        expected=(MEASURING_RANGE, ACCURACY, OUTPUT_SIGNAL, POWER_SUPPLY, PROTECTION, MEDIUM),
    ),
)

DEFAULT_PROFILE = Profile(
    title="Контрольно-измерительный прибор",
    name_keywords=(),
    expected=(MEASURING_RANGE, ACCURACY),
)


def detect_profile(product: ProductInput) -> Profile:
    """Категория по ключевым словам в названии; если не узнали — общий профиль КИП."""
    return next((profile for profile in PROFILES if profile.matches(product.name)), DEFAULT_PROFILE)


def find_missing(product: ProductInput, profile: Profile) -> list[str]:
    """Названия ожидаемых характеристик, которых нет во входных данных."""
    spec_names = [name.lower() for name in product.specs]
    return [spec.title for spec in profile.expected if not spec.is_present(spec_names)]


def _starts_word(prefix: str, text: str) -> bool:
    """Есть ли в тексте слово, начинающееся с prefix: «ду» найдётся в «Ду50», но не в «градуировка»."""
    return re.search(rf"(?<!\w){re.escape(prefix)}", text) is not None
