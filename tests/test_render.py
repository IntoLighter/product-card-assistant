from app.core.models import MISSING, ProductCard
from app.core.pipeline import generate_card
from app.core.render import to_json, to_markdown
from tests.factories import FakeLLM, make_draft, manometer


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


def test_json_round_trip():
    card = build_card()
    text = to_json(card)
    assert text.endswith("\n")
    assert "Манотомь" in text  # кириллица без \uXXXX
    assert ProductCard.model_validate_json(text) == card
