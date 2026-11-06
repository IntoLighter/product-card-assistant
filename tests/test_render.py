from core.models import MISSING, ProductCard
from core.pipeline import generate_card
from core.render import to_json, to_markdown, to_text
from factories import FakeLLM, make_draft, manometer


def build_card(*drafts):
    return generate_card(manometer(), FakeLLM(*(drafts or [make_draft()])))


def test_markdown_has_all_sections():
    markdown = to_markdown(build_card())
    for heading in [
        "# Манометр показывающий DM 02",
        "## SEO-заголовок",
        "## SEO-описание",
        "## Ключевые характеристики",
        "## Поисковые запросы",
        "## Для менеджера",
        "## Требует уточнения",
    ]:
        assert heading in markdown
    assert f"| Измеряемая среда | {MISSING} |" in markdown
    assert "Автоматическая проверка нашла замечания" not in markdown


def test_markdown_shows_unresolved_warnings():
    bad = make_draft(seo_title="М" * 80)
    markdown = to_markdown(build_card(bad, bad, bad))
    assert "> **Автоматическая проверка нашла замечания" in markdown
    assert "> - SEO-заголовок 80 символов" in markdown


def test_table_cells_escaped():
    raw = manometer()
    raw["specs"]["исполнение"] = "общепромышленное | коррозионностойкое"
    card = generate_card(raw, FakeLLM(make_draft()))
    assert "общепромышленное \\| коррозионностойкое" in to_markdown(card)


def test_plain_text_has_content_without_markup():
    text = to_text(build_card())
    assert text.startswith("Манометр показывающий DM 02\n")
    assert "КЛЮЧЕВЫЕ ХАРАКТЕРИСТИКИ\nПроизводитель: Манотомь\n" in text
    assert f"Измеряемая среда: {MISSING}" in text
    assert "Как предложить клиенту: " in text
    for markup in ["#", "**", "| ---", "> "]:
        assert markup not in text


def test_plain_text_shows_unresolved_warnings():
    bad = make_draft(seo_title="М" * 80)
    assert "ЗАМЕЧАНИЯ АВТОМАТИЧЕСКОЙ ПРОВЕРКИ\n- SEO-заголовок 80 символов" in to_text(
        build_card(bad, bad, bad)
    )


def test_json_round_trip():
    card = build_card()
    text = to_json(card)
    assert text.endswith("\n")
    assert "Манотомь" in text  # кириллица без \uXXXX
    assert ProductCard.model_validate_json(text) == card
