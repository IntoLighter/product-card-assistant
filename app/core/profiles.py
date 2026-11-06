"""
Категории приборов и характеристики, которые ожидаются в их карточках.

- Обязательные: без них карточку прибора этой категории публиковать нельзя,
  поэтому генерация не запускается, пока они не заполнены.
- Рекомендуемые: если их нет, карточка показывает «данных нет»,
  а модель получает указание не упоминать их в текстах.

Состав списков — экспертное допущение; его стоит согласовать с контент-менеджером.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from core.models import ProductInput


@dataclass(frozen=True)
class SpecField:
    """Ожидаемая характеристика и начала слов, по которым она узнаётся во входе."""

    title: str
    aliases: tuple[str, ...]

    def is_present(self, spec_names: Iterable[str]) -> bool:
        return any(
            _starts_word(alias, name) for name in spec_names for alias in self.aliases
        )


@dataclass(frozen=True)
class Profile:
    """Категория приборов: как её узнать по названию и что для неё ожидается."""

    title: str
    name_keywords: tuple[str, ...]
    required: tuple[SpecField, ...]
    recommended: tuple[SpecField, ...] = ()

    @property
    def expected(self) -> tuple[SpecField, ...]:
        return (*self.required, *self.recommended)

    def matches(self, product_name: str) -> bool:
        name = product_name.lower()
        return any(keyword in name for keyword in self.name_keywords)


MEASURING_RANGE = SpecField("Диапазон измерений", ("диапазон", "предел"))
ACCURACY = SpecField(
    "Класс точности / погрешность",
    ("класс точности", "точност", "погрешност", "класс допуска"),
)
CONNECTION = SpecField("Присоединение", ("присоедин", "резьб", "штуцер"))
MEDIUM = SpecField("Измеряемая среда", ("сред",))
MEDIUM_TEMPERATURE = SpecField("Температура рабочей среды", ("температур",))
OUTPUT_SIGNAL = SpecField(
    "Выходной сигнал / интерфейс",
    ("выход", "сигнал", "интерфейс", "rs-485", "modbus", "hart"),
)
POWER_SUPPLY = SpecField("Питание", ("питани", "напряжени"))
PROTECTION = SpecField("Степень защиты", ("ip", "степень защиты", "пылевлагозащ"))
CASE_DIAMETER = SpecField("Диаметр корпуса", ("диаметр",))
IMMERSION_LENGTH = SpecField("Длина погружной части", ("длина", "погружн"))
NOMINAL_DIAMETER = SpecField(
    "Диаметр условного прохода (DN)", ("dn", "ду", "условного прохода", "номинальн")
)

PROFILES: tuple[Profile, ...] = (
    Profile(
        title="Манометр (показывающий прибор давления)",
        name_keywords=(
            "манометр",
            "вакуумметр",
            "мановакуумметр",
            "напоромер",
            "тягомер",
        ),
        required=(MEASURING_RANGE, ACCURACY, CONNECTION),
        recommended=(CASE_DIAMETER, MEDIUM, MEDIUM_TEMPERATURE),
    ),
    Profile(
        title="Датчик (преобразователь) давления",
        name_keywords=(
            "датчик давления",
            "преобразователь давления",
            "датчик избыточного",
            "датчик абсолютного",
        ),
        required=(MEASURING_RANGE, ACCURACY, OUTPUT_SIGNAL, POWER_SUPPLY),
        recommended=(CONNECTION, PROTECTION, MEDIUM),
    ),
    Profile(
        title="Датчик температуры / термометр",
        name_keywords=(
            "термометр",
            "термопреобразоват",
            "датчик температуры",
            "термопар",
            "термосопротивлен",
        ),
        required=(MEASURING_RANGE, ACCURACY),
        recommended=(IMMERSION_LENGTH, CONNECTION, OUTPUT_SIGNAL),
    ),
    Profile(
        title="Расходомер / счётчик",
        name_keywords=("расходомер", "счётчик", "счетчик"),
        required=(MEASURING_RANGE, ACCURACY, NOMINAL_DIAMETER),
        recommended=(OUTPUT_SIGNAL, POWER_SUPPLY, PROTECTION),
    ),
    Profile(
        title="Уровнемер / сигнализатор уровня",
        name_keywords=("уровнемер", "сигнализатор уровня", "датчик уровня"),
        required=(MEASURING_RANGE, ACCURACY),
        recommended=(OUTPUT_SIGNAL, POWER_SUPPLY, PROTECTION, MEDIUM),
    ),
)

DEFAULT_PROFILE = Profile(
    title="Контрольно-измерительный прибор",
    name_keywords=(),
    required=(MEASURING_RANGE, ACCURACY),
)


def detect_profile(product: ProductInput) -> Profile:
    """Категория по ключевым словам в названии; если не узнали — общий профиль КИП."""
    return next(
        (profile for profile in PROFILES if profile.matches(product.name)),
        DEFAULT_PROFILE,
    )


def find_missing(product: ProductInput, profile: Profile) -> list[str]:
    """
    Ожидаемые характеристики, которых нет во входных данных.

    И обязательные, и рекомендуемые.
    """
    return _missing(product, profile.expected)


def find_missing_required(product: ProductInput, profile: Profile) -> list[str]:
    """Названия обязательных характеристик, которых нет во входных данных."""
    return _missing(product, profile.required)


def _missing(product: ProductInput, fields: Iterable[SpecField]) -> list[str]:
    spec_names = [name.lower() for name in product.specs]
    return [field.title for field in fields if not field.is_present(spec_names)]


def _starts_word(prefix: str, text: str) -> bool:
    """
    Есть ли в тексте слово, начинающееся с prefix.

    «ду» найдётся в «Ду50», но не в «градуировка».
    """
    return re.search(rf"(?<!\w){re.escape(prefix)}", text) is not None
