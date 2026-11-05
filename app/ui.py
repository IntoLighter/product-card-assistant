"""
Веб-интерфейс для контент-менеджера.

    uv run streamlit run app/ui.py
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

from app.core.config import Settings
from app.core.llm import LLMError, OpenAICompatibleClient
from app.core.pipeline import generate_card
from app.core.render import to_json, to_markdown
from app.core.validation import InputError, parse_json

if TYPE_CHECKING:
    from app.core.models import ProductCard
    from app.core.validation import RawProduct

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

MODE_JSON = "JSON"
MODE_FORM = "Форма"
SPEC_NAME = "Характеристика"
SPEC_VALUE = "Значение"
JSON_PLACEHOLDER = '{"name": "...", "manufacturer": "...", "specs": {"...": "..."}, "description": "..."}'

# Ключи st.session_state
JSON_TEXT_KEY = "json_text"
EXAMPLE_KEY = "example"
UPLOADED_FILE_KEY = "uploaded_file_id"
RESULTS_KEY = "results"


@dataclass(frozen=True)
class GenerationResult:
    """Итог по одному товару: карточка или текст ошибки."""

    label: str
    card: ProductCard | None = None
    error: str | None = None


@st.cache_resource
def get_llm() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(Settings.from_env())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    st.set_page_config(page_title="Карточки КИП", layout="wide")
    llm = get_llm()
    llm_ready = render_sidebar(llm)

    st.title("Черновик карточки товара КИП")
    st.caption("Технические значения берутся только из входных данных. Чего нет — помечается «данных нет».")

    input_column, output_column = st.columns([2, 3], gap="large")
    with input_column:
        products_json = render_input()
        generate_clicked = st.button("Сгенерировать", type="primary", width="stretch", disabled=not llm_ready)
    with output_column:
        if generate_clicked:
            st.session_state[RESULTS_KEY] = generate_all(products_json, llm)
        render_results(st.session_state.get(RESULTS_KEY, []))


# --- Боковая панель ---------------------------------------------------------


def render_sidebar(llm: OpenAICompatibleClient) -> bool:
    """Статус модели и загрузка примеров. Возвращает, готова ли модель."""
    with st.sidebar:
        st.header("Модель")
        status = llm.check_server()
        if status.ready:
            st.success(status.message)
        else:
            st.error(status.message)
            st.caption("Первый запуск vLLM: скачивание и загрузка модели занимают несколько минут.")
        st.button("Обновить статус")
        st.caption(
            f"Сервер: `{llm.settings.base_url}`  \n"
            f"Temperature: {llm.settings.temperature}, попыток исправления: {llm.settings.max_attempts - 1}"
        )

        st.header("Примеры")
        examples = sorted(path.name for path in EXAMPLES_DIR.glob("*.json"))
        st.selectbox(
            "Загрузить в поле JSON",
            ["", *examples],
            key=EXAMPLE_KEY,
            on_change=_load_selected_example,
            format_func=lambda name: name or "— выберите —",
        )
    return status.ready


def _load_selected_example() -> None:
    name = st.session_state.get(EXAMPLE_KEY)
    if name:
        st.session_state[JSON_TEXT_KEY] = (EXAMPLES_DIR / name).read_text(encoding="utf-8")


# --- Ввод -------------------------------------------------------------------


def render_input() -> str:
    """Поле JSON или форма. В обоих случаях возвращается JSON-текст, дальше путь один."""
    mode = st.segmented_control("Способ ввода", [MODE_JSON, MODE_FORM], default=MODE_JSON, label_visibility="collapsed")
    return _form_input() if mode == MODE_FORM else _json_input()


def _json_input() -> str:
    uploaded = st.file_uploader("JSON-файл", type=["json"])
    if uploaded is not None and st.session_state.get(UPLOADED_FILE_KEY) != uploaded.file_id:
        st.session_state[UPLOADED_FILE_KEY] = uploaded.file_id
        st.session_state[JSON_TEXT_KEY] = uploaded.getvalue().decode("utf-8", errors="replace")
    return st.text_area("JSON товара (объект или массив)", key=JSON_TEXT_KEY, height=380, placeholder=JSON_PLACEHOLDER)


def _form_input() -> str:
    name = st.text_input("Название *", key="form_name", placeholder="Манометр показывающий DM 02")
    manufacturer = st.text_input("Производитель", key="form_manufacturer")
    st.caption("Характеристики: строки можно добавлять и удалять.")
    rows = st.data_editor([{SPEC_NAME: "", SPEC_VALUE: ""}], num_rows="dynamic", width="stretch", key="form_specs")
    description = st.text_area("Описание / фрагмент паспорта", key="form_description", height=150)

    specs = {str(row[SPEC_NAME]).strip(): str(row.get(SPEC_VALUE) or "") for row in rows if row.get(SPEC_NAME)}
    product = {"name": name, "manufacturer": manufacturer, "specs": specs, "description": description}
    return json.dumps(product, ensure_ascii=False)


# --- Генерация и результат --------------------------------------------------


def generate_all(products_json: str, llm: OpenAICompatibleClient) -> list[GenerationResult]:
    try:
        products = parse_json(products_json)
    except InputError as error:
        return [GenerationResult(label="Входные данные", error=str(error))]
    return [_generate_one(raw, number, llm) for number, raw in enumerate(products, start=1)]


def _generate_one(raw: RawProduct, number: int, llm: OpenAICompatibleClient) -> GenerationResult:
    label = str(raw.get("name") or f"Товар №{number}")
    with st.spinner(f"Генерация: {label}…"):
        try:
            card = generate_card(raw, llm, max_attempts=llm.settings.max_attempts)
        except (InputError, LLMError) as error:
            return GenerationResult(label=label, error=str(error))
    return GenerationResult(label=label, card=card)


def render_results(results: list[GenerationResult]) -> None:
    if not results:
        st.info("Вставьте JSON или заполните форму и нажмите «Сгенерировать».")
        return
    for index, result in enumerate(results):
        if result.card is None:
            st.error(f"{result.label}: {result.error}")
            continue
        if len(results) > 1:
            st.subheader(result.label)
        render_card(result.card, key=str(index))
        st.divider()


def render_card(card: ProductCard, key: str) -> None:
    if card.meta.checks_passed:
        st.success("Все проверки пройдены: длины в норме, чисел и терминов вне входных данных нет.")
    for warning in card.check_warnings:
        st.warning(warning.message)
    if card.ignored_fields:
        st.info(f"Не используются поля входа: {', '.join(card.ignored_fields)}.")

    markdown, json_text = to_markdown(card), to_json(card)
    preview_tab, markdown_tab, json_tab = st.tabs(["Карточка", "Markdown", "JSON"])
    preview_tab.markdown(markdown)
    # У st.code есть встроенная кнопка копирования
    markdown_tab.code(markdown, language="markdown")
    json_tab.code(json_text, language="json")

    markdown_column, json_column = st.columns(2)
    markdown_column.download_button(
        "Скачать .md", markdown, f"card_{key}.md", mime="text/markdown", key=f"download_md_{key}"
    )
    json_column.download_button(
        "Скачать .json", json_text, f"card_{key}.json", mime="application/json", key=f"download_json_{key}"
    )


if __name__ == "__main__":
    main()
