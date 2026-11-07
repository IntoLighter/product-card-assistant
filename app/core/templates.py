"""
Шаблоны формы по типам приборов: название типа и обязательные для него характеристики.

Шаблоны лежат JSON-файлами в resources/templates/,
поэтому их может править не программист:

    {
        "name": "Манометр",
        "specs": ["Диапазон измерений", "Класс точности", "Присоединение"]
    }

Что каждый шаблон совпадает с обязательными характеристиками своего профиля
из profiles.py, проверяют тесты.
"""

from pydantic import BaseModel, ConfigDict, Field

from core.resources import templates_dir
from core.validation import RawProduct

# Подпись шаблона без названия: для приборов, которых нет среди известных типов
OTHER_DEVICE_LABEL = "Другой прибор"


class ProductTemplate(BaseModel):
    """Шаблон в файле: название типа прибора и список обязательных характеристик."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    specs: list[str] = Field(min_length=1)

    @property
    def label(self) -> str:
        return self.name or OTHER_DEVICE_LABEL

    def to_raw_product(self) -> RawProduct:
        """Товар для формы: название типа и характеристики без значений."""
        return RawProduct(name=self.name, specs=dict.fromkeys(self.specs, ""))


def load_templates() -> dict[str, RawProduct]:
    """
    Шаблоны для формы в виде {подпись для списка: товар для формы}.

    Шаблоны идут по алфавиту, «Другой прибор» — последним.
    """
    templates = [
        ProductTemplate.model_validate_json(path.read_bytes())
        for path in templates_dir().glob("*.json")
    ]
    templates.sort(key=lambda template: (not template.name, template.name))
    return {template.label: template.to_raw_product() for template in templates}
