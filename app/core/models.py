"""
Модели данных: вход, ответ LLM и итоговая карточка.

Ограничения из ТЗ (длины текстов, число запросов) объявлены здесь один раз:
их используют JSON-схема ответа, промпт и автоматическая проверка.
"""

from pydantic import BaseModel, ConfigDict, Field

MISSING = "данных нет"

TITLE_MAX_LEN = 70
DESCRIPTION_MIN_LEN = 800
DESCRIPTION_MAX_LEN = 1200
# Середина диапазона: ориентир для модели и для подсказок при исправлении длины
DESCRIPTION_TARGET_LEN = 1000
QUERIES_MIN = 3
QUERIES_MAX = 5
COMMERCIAL_ITEMS_MAX = 4


class ProductInput(BaseModel):
    """Нормализованные входные данные: без лишних пробелов и пустых значений."""

    name: str
    manufacturer: str | None = None
    specs: dict[str, str] = Field(default_factory=dict)
    description: str | None = None


class Issue(BaseModel):
    """Замечание к входным данным или к ответу модели."""

    field: str
    message: str


class Commercial(BaseModel):
    """Блок для менеджера: кому подходит прибор и какие задачи решает."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    audience: list[str] = Field(min_length=1, max_length=COMMERCIAL_ITEMS_MAX)
    tasks: list[str] = Field(min_length=1, max_length=COMMERCIAL_ITEMS_MAX)
    pitch: str


class LLMDraft(BaseModel):
    """
    Ответ модели; по этой модели строится JSON-схема структурированного вывода.

    Технических характеристик и списка уточнений здесь нет намеренно: их собирает код
    из входных данных, а модель в них только добавляла бы шум.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    seo_title: str
    seo_description: str
    search_queries: list[str] = Field(min_length=QUERIES_MIN, max_length=QUERIES_MAX)
    commercial: Commercial


class SpecRow(BaseModel):
    """Строка таблицы характеристик."""

    name: str
    value: str
    is_missing: bool = False


class CardMeta(BaseModel):
    """Служебные сведения о генерации."""

    llm_model: str
    attempts: int
    seo_title_length: int
    seo_description_length: int
    checks_passed: bool


class ProductCard(BaseModel):
    """Черновик карточки товара для контент-менеджера."""

    product_name: str
    manufacturer: str
    category: str
    seo_title: str
    seo_description: str
    specs: list[SpecRow]
    search_queries: list[str]
    commercial: Commercial
    # Чего не хватает во входных данных — что уточнить у поставщика
    needs_clarification: list[str]
    # Замечания автоматической проверки, которые модель не исправила
    check_warnings: list[Issue]
    # Поля входа, которые сервис не использует
    ignored_fields: list[str]
    meta: CardMeta
