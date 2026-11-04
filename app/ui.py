"""Веб-интерфейс: uv run streamlit run app/ui.py"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from app.core.config import Settings
from app.core.llm import LLMError, OpenAICompatibleClient
from app.core.pipeline import generate_card
from app.core.render import to_json, to_markdown
from app.core.schema import ProductCard
from app.core.validation import InputError, parse_json

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

st.set_page_config(page_title="Карточки КИП", layout="wide")


@st.cache_resource
def get_llm() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(Settings.from_env())


def load_example() -> None:
    name = st.session_state.get("example")
    if name:
        st.session_state["json_text"] = (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def form_to_raw() -> dict:
    specs_df: pd.DataFrame = st.session_state.get("form_specs", pd.DataFrame())
    specs = {}
    for _, row in specs_df.iterrows():
        key = str(row.get("Характеристика") or "").strip()
        if key:
            value = row.get("Значение")
            specs[key] = "" if pd.isna(value) else str(value)
    return {
        "name": st.session_state.get("form_name", ""),
        "manufacturer": st.session_state.get("form_manufacturer", ""),
        "specs": specs,
        "description": st.session_state.get("form_description", ""),
    }


def show_card(card: ProductCard, idx: int) -> None:
    md, js = to_markdown(card), to_json(card)
    if card.meta.get("checks_passed"):
        st.success("Все проверки пройдены: длины в норме, чисел и терминов вне входных данных нет.")
    for issue in card.issues:
        (st.warning if issue.level != "info" else st.info)(issue.message)

    view, md_tab, json_tab = st.tabs(["Карточка", "Markdown", "JSON"])
    with view:
        st.markdown(md)
    with md_tab:
        st.code(md, language="markdown")  # у st.code есть кнопка копирования
    with json_tab:
        st.code(js, language="json")

    stem = f"card_{idx}"
    c1, c2 = st.columns(2)
    c1.download_button("Скачать .md", md, f"{stem}.md", "text/markdown", key=f"dl_md_{idx}")
    c2.download_button("Скачать .json", js, f"{stem}.json", "application/json", key=f"dl_js_{idx}")


# --- Боковая панель -----------------------------------------------------------
llm = get_llm()
with st.sidebar:
    st.header("Модель")
    ok, status = llm.health()
    (st.success if ok else st.error)(status)
    if not ok:
        st.caption("Первый запуск vLLM: скачивание и загрузка модели занимают несколько минут.")
    st.button("Обновить статус")
    st.caption(f"Сервер: `{llm.settings.base_url}`  \nTemperature: {llm.settings.temperature}, "
               f"попыток исправления: {llm.settings.max_attempts - 1}")

    st.header("Примеры")
    examples = sorted(p.name for p in EXAMPLES_DIR.glob("*.json"))
    st.selectbox("Загрузить в поле JSON", [""] + examples, key="example", on_change=load_example,
                 format_func=lambda x: x or "— выберите —")

# --- Ввод -------------------------------------------------------------------
st.title("Черновик карточки товара КИП")
st.caption("Технические значения берутся только из входных данных. Чего нет — помечается «данных нет».")

left, right = st.columns([2, 3], gap="large")

with left:
    mode = st.segmented_control("Ввод", ["JSON", "Форма"], default="JSON", label_visibility="collapsed")

    if mode == "Форма":
        st.text_input("Название *", key="form_name", placeholder="Манометр показывающий DM 02")
        st.text_input("Производитель", key="form_manufacturer")
        st.caption("Характеристики (строки можно добавлять и удалять)")
        st.session_state["form_specs"] = st.data_editor(
            pd.DataFrame([{"Характеристика": "", "Значение": ""}]),
            num_rows="dynamic", width="stretch", key="form_specs_editor",
        )
        st.text_area("Описание / фрагмент паспорта", key="form_description", height=150)
    else:
        uploaded = st.file_uploader("JSON-файл", type=["json"])
        if uploaded is not None and st.session_state.get("uploaded_id") != uploaded.file_id:
            st.session_state["uploaded_id"] = uploaded.file_id
            st.session_state["json_text"] = uploaded.getvalue().decode("utf-8", errors="replace")
        st.text_area("JSON товара (объект или массив)", key="json_text", height=380,
                     placeholder='{"name": "...", "manufacturer": "...", "specs": {...}, "description": "..."}')

    generate = st.button("Сгенерировать", type="primary", width="stretch", disabled=not ok)

# --- Генерация --------------------------------------------------------------
if generate:
    st.session_state["results"] = []
    try:
        items = [form_to_raw()] if mode == "Форма" else parse_json(st.session_state.get("json_text", ""))
    except InputError as e:
        st.session_state["results"] = [("error", str(e))]
        items = []

    for i, raw in enumerate(items, 1):
        label = str(raw.get("name") or f"товар №{i}")
        with right, st.spinner(f"Генерация: {label}…"):
            try:
                card = generate_card(raw, llm, llm.settings.max_attempts, llm.settings.model)
                st.session_state["results"].append(("card", card))
            except (InputError, LLMError) as e:
                st.session_state["results"].append(("error", f"{label}: {e}"))

with right:
    results = st.session_state.get("results", [])
    if not results:
        st.info("Вставьте JSON или заполните форму и нажмите «Сгенерировать».")
    for idx, (kind, payload) in enumerate(results):
        if kind == "error":
            st.error(payload)
        else:
            if len(results) > 1:
                st.subheader(payload.product_name)
            show_card(payload, idx)
            st.divider()
