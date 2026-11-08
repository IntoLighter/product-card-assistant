"""
Шаблоны по типам приборов: всё, что сервис знает о категории прибора.

Шаблоны лежат JSON-файлами в resources/templates/,
поэтому их может править не программист:

    {
        "name": "Манометр",
        "category": "Манометр (показывающий прибор давления)",
        "keywords": ["манометр", "вакуумметр"],
        "required": {
            "Диапазон измерений": ["диапазон", "предел"],
            "Класс точности": ["точност", "погрешност"]
        },
        "recommended": {
            "Измеряемая среда": ["сред"]
        }
    }

- name: подпись в списке шаблонов формы; пустое — «Другой прибор».
- category: категория в карточке и в промпте.
- keywords: по ним шаблон узнаётся в названии товара. Шаблон без ключевых слов
  один: он берётся, если не подошёл ни один другой.
- required: обязательные характеристики. Они подставляются в форму, и без них
  генерация не запускается.
- recommended: рекомендуемые характеристики. Если их нет, карточка показывает
  «данных нет», а модель получает указание не упоминать их в текстах.

У каждой характеристики — начала слов, по которым она узнаётся во входе
(«погрешност» засчитывает «основная приведённая погрешность» как класс точности).
Само название характеристики узнаётся всегда.

Состав списков — экспертное допущение; его стоит согласовать с контент-менеджером.
"""

import re
from collections.abc import Iterable, Mapping
from functools import cache

from pydantic import BaseModel, ConfigDict, Field

from core.models import ProductInput, RawProduct
from core.resources import templates_dir

# Подпись шаблона без названия: для приборов, которых нет среди известных типов
OTHER_DEVICE_LABEL = "Другой прибор"

# Название характеристики -> начала слов, по которым она узнаётся во входе
type SpecAliases = dict[str, list[str]]


class ProductTemplate(BaseModel):
    """Шаблон типа прибора из файла."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = ""
    category: str
    keywords: list[str] = []
    required: SpecAliases = Field(min_length=1)
    recommended: SpecAliases = {}

    @property
    def label(self) -> str:
        return self.name or OTHER_DEVICE_LABEL

    def matches(self, product_name: str) -> bool:
        product_name = product_name.lower()
        return any(keyword.lower() in product_name for keyword in self.keywords)

    def to_raw_product(self) -> RawProduct:
        """Товар для формы: название типа и обязательные характеристики без значений."""
        return RawProduct(name=self.name, specs=dict.fromkeys(self.required, ""))

    def find_missing(self, product: ProductInput) -> list[str]:
        """Обязательные и рекомендуемые характеристики, которых нет во входе."""
        return _missing(product, {**self.required, **self.recommended})

    def find_missing_required(self, product: ProductInput) -> list[str]:
        """Обязательные характеристики, которых нет во входе."""
        return _missing(product, self.required)


@cache
def load_templates() -> tuple[ProductTemplate, ...]:
    """
    Шаблоны из resources/templates/, читаются один раз за запуск.

    Идут по алфавиту, «Другой прибор» — последним. После правки JSON
    приложение нужно перезапустить.
    """
    templates = sorted(
        (
            ProductTemplate.model_validate_json(path.read_bytes())
            for path in templates_dir().glob("*.json")
        ),
        key=lambda template: (not template.name, template.name),
    )
    defaults = [template.label for template in templates if not template.keywords]
    if len(defaults) != 1:
        raise ValueError(
            "Шаблон без ключевых слов должен быть ровно один, "
            f"а их {len(defaults)}: {', '.join(defaults)}."
        )
    return tuple(templates)


def detect_template(product: ProductInput) -> ProductTemplate:
    """Шаблон по ключевым словам в названии; если не узнали — «Другой прибор»."""
    templates = load_templates()
    return next(
        (template for template in templates if template.matches(product.name)),
        next(template for template in templates if not template.keywords),
    )


def _missing(product: ProductInput, fields: Mapping[str, list[str]]) -> list[str]:
    spec_names = [name.lower() for name in product.specs]
    return [
        title
        for title, aliases in fields.items()
        if not _is_present([title.lower(), *aliases], spec_names)
    ]


def _is_present(aliases: Iterable[str], spec_names: list[str]) -> bool:
    return any(
        _starts_word(alias.lower(), name) for name in spec_names for alias in aliases
    )


def _starts_word(prefix: str, text: str) -> bool:
    """
    Есть ли в тексте слово, начинающееся с prefix.

    «ду» найдётся в «Ду50», но не в «градуировка».
    """
    return re.search(rf"(?<!\w){re.escape(prefix)}", text) is not None
