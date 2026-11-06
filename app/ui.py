"""
Веб-интерфейс для контент-менеджера.

    uv run streamlit run app/ui.py
"""

import logging
import re
from dataclasses import dataclass

import streamlit as st

from core.config import Settings
from core.llm import LLMError, OpenAICompatibleClient
from core.models import ProductCard
from core.pipeline import generate_card
from core.render import to_json, to_markdown, to_text
from core.templates import load_templates
from core.validation import (
    InputError,
    RawProduct,
    ensure_required_specs,
    normalize_product,
    parse_json,
)

SPEC_NAME = "Характеристика"
SPEC_VALUE = "Значение"
EMPTY_SPECS = [{SPEC_NAME: "", SPEC_VALUE: ""}]

# Ключи st.session_state
TEMPLATE_KEY = "template"
NAME_KEY = "form_name"
MANUFACTURER_KEY = "form_manufacturer"
DESCRIPTION_KEY = "form_description"
SPECS_KEY = "form_specs"
# st.data_editor нельзя заполнить из кода:
# при заполнении формы пересоздаём его с новым ключом
SPECS_EDITOR_VERSION_KEY = "form_specs_version"
UPLOAD_KEY = "upload"
UPLOAD_ERROR_KEY = "upload_error"
UPLOAD_NOTE_KEY = "upload_note"
RESULT_KEY = "result"


@dataclass(frozen=True)
class GenerationResult:
    """Готовая карточка или текст ошибки."""

    card: ProductCard | None = None
    error: str | None = None


@st.cache_resource
def get_llm() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(Settings())


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    st.set_page_config(page_title="Карточки КИП", layout="wide")
    llm = get_llm()

    st.title("Карточки КИП")
    if not ensure_model_ready(llm):
        return

    form_column, result_column = st.columns([2, 3], gap="large")
    with form_column:
        raw = render_form()
        blocked_reason = _generation_blocked_reason(raw)
        generate_clicked = st.button(
            "Сгенерировать",
            type="primary",
            width="stretch",
            disabled=blocked_reason is not None,
        )
        if blocked_reason:
            st.caption(blocked_reason)
    with result_column:
        if generate_clicked:
            st.session_state[RESULT_KEY] = generate(raw, llm)
        render_result(st.session_state.get(RESULT_KEY))


# --- Статус модели ----------------------------------------------------------


def ensure_model_ready(llm: OpenAICompatibleClient) -> bool:
    """
    Готова ли модель. Если нет — показывает причину вместо интерфейса.

    Пока модель недоступна, форма бесполезна, поэтому её не показываем;
    когда всё в порядке, статус не занимает место на экране.
    """
    status = llm.check_server()
    if status.ready:
        return True
    st.error(status.message)
    st.caption(
        "Первый запуск vLLM: скачивание и загрузка модели занимают несколько минут."
    )
    st.button("Проверить снова")
    return False


# --- Форма ------------------------------------------------------------------


def render_form() -> RawProduct:
    """Форма товара; возвращает данные в том же виде, что и входной JSON."""
    template_tab, json_tab = st.tabs(["Шаблон", "JSON"])
    with template_tab:
        st.selectbox(
            "Заполнить из шаблона",
            ["", *load_templates()],
            key=TEMPLATE_KEY,
            on_change=_fill_form_from_template,
            format_func=lambda label: label or "— пустая форма —",
        )
    with json_tab:
        st.file_uploader(
            "Загрузить из JSON",
            type=["json"],
            key=UPLOAD_KEY,
            on_change=_fill_form_from_file,
        )
        if error := st.session_state.get(UPLOAD_ERROR_KEY):
            st.error(error)
        if note := st.session_state.get(UPLOAD_NOTE_KEY):
            st.info(note)

    name = st.text_input(
        "Название *", key=NAME_KEY, placeholder="Манометр показывающий DM 02"
    )
    manufacturer = st.text_input("Производитель", key=MANUFACTURER_KEY)
    st.caption("Характеристики: строки можно добавлять и удалять.")
    rows = st.data_editor(
        st.session_state.get(SPECS_KEY, EMPTY_SPECS),
        num_rows="dynamic",
        width="stretch",
        key=f"specs_editor_{st.session_state.get(SPECS_EDITOR_VERSION_KEY, 0)}",
    )
    description = st.text_area(
        "Описание / фрагмент паспорта", key=DESCRIPTION_KEY, height=150
    )

    specs = {
        str(row[SPEC_NAME]).strip(): str(row.get(SPEC_VALUE) or "")
        for row in rows
        if row.get(SPEC_NAME)
    }
    return {
        "name": name,
        "manufacturer": manufacturer,
        "specs": specs,
        "description": description,
    }


def _generation_blocked_reason(raw: RawProduct) -> str | None:
    """
    Почему генерацию сейчас нельзя запустить; None — можно.

    Обязательны название и характеристики, обязательные по профилю категории;
    прочие пробелы сервис не запрещает, а помечает «данных нет».
    """
    if not str(raw.get("name") or "").strip():
        return "Заполните обязательное поле «Название»."
    try:
        ensure_required_specs(normalize_product(raw).product)
    except InputError as error:
        return str(error)
    return None


def _fill_form_from_template() -> None:
    """Подставляет выбранный шаблон в поля формы; пустой выбор очищает форму."""
    label = st.session_state.get(TEMPLATE_KEY)
    _fill_form(load_templates().get(label, {}) if label else {})


def _fill_form_from_file() -> None:
    """Подставляет товар из загруженного JSON-файла; при ошибке форма не меняется."""
    uploaded = st.session_state.get(UPLOAD_KEY)
    if uploaded is None:  # файл убрали из поля загрузки — форму не трогаем
        return
    try:
        products = parse_json(uploaded.getvalue().decode("utf-8"))
    except (UnicodeDecodeError, InputError) as error:
        _clear_upload_messages()
        st.session_state[UPLOAD_ERROR_KEY] = (
            f"Не удалось загрузить {uploaded.name}: {error}"
        )
        return

    _fill_form(products[0])
    st.session_state[TEMPLATE_KEY] = (
        ""  # иначе в списке осталось бы имя прежнего шаблона
    )
    if len(products) > 1:
        st.session_state[UPLOAD_NOTE_KEY] = (
            f"Товаров в файле: {len(products)}. Загружен первый."
        )


def _fill_form(raw: RawProduct) -> None:
    """Заполняет поля формы данными товара в формате входного JSON."""
    _clear_upload_messages()
    st.session_state[NAME_KEY] = _as_text(raw.get("name"))
    st.session_state[MANUFACTURER_KEY] = _as_text(raw.get("manufacturer"))
    st.session_state[DESCRIPTION_KEY] = _as_text(raw.get("description"))
    specs = raw.get("specs")
    rows = (
        [{SPEC_NAME: key, SPEC_VALUE: _as_text(value)} for key, value in specs.items()]
        if isinstance(specs, dict)
        else []
    )
    st.session_state[SPECS_KEY] = rows or EMPTY_SPECS
    st.session_state[SPECS_EDITOR_VERSION_KEY] = (
        st.session_state.get(SPECS_EDITOR_VERSION_KEY, 0) + 1
    )
    st.session_state[RESULT_KEY] = None


def _clear_upload_messages() -> None:
    st.session_state[UPLOAD_ERROR_KEY] = None
    st.session_state[UPLOAD_NOTE_KEY] = None


def _as_text(value: object) -> str:
    return "" if value is None else str(value)


# --- Генерация и результат --------------------------------------------------


def generate(raw: RawProduct, llm: OpenAICompatibleClient) -> GenerationResult:
    with st.spinner("Генерация карточки…"):
        try:
            card = generate_card(raw, llm, max_attempts=llm.settings.max_attempts)
        except (InputError, LLMError) as error:
            return GenerationResult(error=str(error))
    return GenerationResult(card=card)


def render_result(result: GenerationResult | None) -> None:
    if result is None:
        st.info("Выберите шаблон или заполните форму и нажмите «Сгенерировать».")
    elif result.card is None:
        st.error(result.error)
    else:
        render_card(result.card)


def render_card(card: ProductCard) -> None:
    for warning in card.check_warnings:
        st.warning(warning.message)

    markdown = to_markdown(card)
    preview_tab, text_tab, markdown_tab, json_tab = st.tabs(
        ["Карточка", "Текст", "Markdown", "JSON"]
    )
    preview_tab.markdown(markdown)
    stem = _file_stem(card.product_name)
    with text_tab:
        _copyable(
            to_text(card), language=None, file_name=f"{stem}.txt", mime="text/plain"
        )
    with markdown_tab:
        _copyable(
            markdown, language="markdown", file_name=f"{stem}.md", mime="text/markdown"
        )
    with json_tab:
        _copyable(
            to_json(card),
            language="json",
            file_name=f"{stem}.json",
            mime="application/json",
        )


def _copyable(content: str, *, language: str | None, file_name: str, mime: str) -> None:
    """Кнопка скачивания и блок с кнопкой копирования (значок в углу st.code)."""
    st.download_button(
        "Скачать", content, file_name, mime=mime, icon=":material/download:"
    )
    st.code(content, language=language, wrap_lines=True)


def _file_stem(product_name: str) -> str:
    """Имя файла из названия товара без символов, запрещённых в Windows."""
    return re.sub(r'[\\/:*?"<>|]+', "_", product_name).strip(" .") or "card"


if __name__ == "__main__":
    main()
