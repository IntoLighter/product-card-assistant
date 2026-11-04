"""Профили категорий КИП: какие характеристики ожидаются в карточке.

Нужны, чтобы явно показать «данных нет» по важным полям, которых нет во входе,
а не молча их пропускать. Сопоставление — по началу слова в названиях характеристик.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import ProductInput

# Каноническое название -> начала слов, по которым узнаём его во входных ключах
RANGE = ("Диапазон измерений", ("диапазон", "предел"))
ACCURACY = ("Класс точности / погрешность", ("класс точности", "точност", "погрешност", "класс допуска"))
CONNECTION = ("Присоединение", ("присоедин", "резьб", "штуцер"))
MEDIUM = ("Измеряемая среда", ("сред",))
OUTPUT = ("Выходной сигнал / интерфейс", ("выход", "сигнал", "интерфейс", "rs-485", "modbus", "hart"))
POWER = ("Питание", ("питани", "напряжени"))
PROTECTION = ("Степень защиты", ("ip", "степень защиты", "пылевлагозащ"))
TEMPERATURE = ("Температура рабочей среды", ("температур",))


@dataclass(frozen=True)
class Profile:
    title: str
    keywords: tuple[str, ...]
    expected: tuple[tuple[str, tuple[str, ...]], ...]


PROFILES: tuple[Profile, ...] = (
    Profile(
        "Манометр (показывающий прибор давления)",
        ("манометр", "вакуумметр", "мановакуумметр", "напоромер", "тягомер"),
        (RANGE, ACCURACY, CONNECTION, ("Диаметр корпуса", ("диаметр",)), MEDIUM, TEMPERATURE),
    ),
    Profile(
        "Датчик (преобразователь) давления",
        ("датчик давления", "преобразователь давления", "датчик избыточного", "датчик абсолютного"),
        (RANGE, ACCURACY, OUTPUT, POWER, CONNECTION, PROTECTION, MEDIUM),
    ),
    Profile(
        "Датчик температуры / термометр",
        ("термометр", "термопреобразоват", "датчик температуры", "термопар", "термосопротивлен"),
        (RANGE, ACCURACY, ("Длина погружной части", ("длина", "погружн")), CONNECTION, OUTPUT),
    ),
    Profile(
        "Расходомер / счётчик",
        ("расходомер", "счётчик", "счетчик"),
        (RANGE, ACCURACY, ("Диаметр условного прохода (DN)", ("dn", "ду", "условного прохода", "номинальн")),
         OUTPUT, POWER, PROTECTION),
    ),
    Profile(
        "Уровнемер / сигнализатор уровня",
        ("уровнемер", "сигнализатор уровня", "датчик уровня"),
        (RANGE, ACCURACY, OUTPUT, POWER, PROTECTION, MEDIUM),
    ),
)

DEFAULT_PROFILE = Profile("Контрольно-измерительный прибор", (), (RANGE, ACCURACY))


def detect_profile(product: ProductInput) -> Profile:
    name = product.name.lower()
    for profile in PROFILES:
        if any(k in name for k in profile.keywords):
            return profile
    return DEFAULT_PROFILE


def find_missing(product: ProductInput, profile: Profile) -> list[str]:
    """Ожидаемые для категории характеристики, которых нет во входе."""
    keys = [k.lower() for k in product.specs]
    return [
        canonical
        for canonical, needles in profile.expected
        if not any(_starts_word(n, key) for key in keys for n in needles)
    ]


def _starts_word(needle: str, text: str) -> bool:
    """Подстрока с начала слова: «ду» найдётся в «Ду50», но не в «градуировка»."""
    return re.search(r"(?<!\w)" + re.escape(needle), text) is not None
