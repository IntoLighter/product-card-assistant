"""Модели данных: вход, ответ LLM, итоговая карточка."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MISSING = "данных нет"

TITLE_MAX = 70
DESCRIPTION_MIN, DESCRIPTION_MAX = 800, 1200
QUERIES_MIN, QUERIES_MAX = 3, 5


class ProductInput(BaseModel):
    name: str
    manufacturer: str | None = None
    specs: dict[str, str] = Field(default_factory=dict)
    description: str | None = None


class Issue(BaseModel):
    """Замечание для контент-менеджера (или для модели при повторной генерации)."""

    level: Literal["error", "warning", "info"]
    field: str
    message: str


# --- Ответ LLM ---------------------------------------------------------------


class Commercial(BaseModel):
    audience: list[str]
    tasks: list[str]
    pitch: str


class LLMDraft(BaseModel):
    seo_title: str
    seo_description: str
    search_queries: list[str]
    commercial: Commercial
    clarifications: list[str] = Field(default_factory=list)


# JSON-схема для structured output (vLLM / xgrammar). Пишем вручную, без $ref,
# чтобы она гарантированно поддерживалась бэкендом грамматик.
_STR_LIST = {"type": "array", "items": {"type": "string"}}
LLM_DRAFT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "seo_title": {"type": "string"},
        "seo_description": {"type": "string"},
        "search_queries": {**_STR_LIST, "minItems": QUERIES_MIN, "maxItems": QUERIES_MAX},
        "commercial": {
            "type": "object",
            "properties": {
                "audience": {**_STR_LIST, "minItems": 1, "maxItems": 4},
                "tasks": {**_STR_LIST, "minItems": 1, "maxItems": 4},
                "pitch": {"type": "string"},
            },
            "required": ["audience", "tasks", "pitch"],
            "additionalProperties": False,
        },
        "clarifications": _STR_LIST,
    },
    "required": ["seo_title", "seo_description", "search_queries", "commercial", "clarifications"],
    "additionalProperties": False,
}


# --- Итоговая карточка -------------------------------------------------------


class SpecRow(BaseModel):
    name: str
    value: str
    source: Literal["input", "missing"]  # missing -> «данных нет», значение не выдумываем


class ProductCard(BaseModel):
    product_name: str
    manufacturer: str
    category: str
    seo_title: str
    seo_description: str
    specs: list[SpecRow]
    search_queries: list[str]
    commercial: Commercial
    needs_clarification: list[str]
    issues: list[Issue]
    meta: dict = Field(default_factory=dict)
