import pytest

from app.core.schema import Commercial, LLMDraft

MANOMETER = {
    "name": "Манометр показывающий DM 02",
    "manufacturer": "Манотомь",
    "specs": {"диапазон измерений": "0–1,6 МПа", "класс точности": "1,5",
              "присоединение": "G1/2", "диаметр корпуса": "100 мм"},
    "description": "Прибор предназначен для измерения избыточного давления.",
}

GOOD_DESCRIPTION = (
    "Манометр показывающий DM 02 производства Манотомь предназначен для измерения избыточного давления "
    "и визуального контроля его значения непосредственно на месте установки. "
) * 4 + (
    "Диапазон измерений 0–1,6 МПа, класс точности 1,5, присоединение G1/2, диаметр корпуса 100 мм. "
) * 2


def make_draft(**overrides) -> LLMDraft:
    data = dict(
        seo_title="Манометр показывающий DM 02 Манотомь, 0–1,6 МПа",
        seo_description=GOOD_DESCRIPTION,
        search_queries=["манометр dm 02", "манометр манотомь", "манометр 1,6 мпа"],
        commercial=Commercial(audience=["службы КИПиА"], tasks=["контроль давления"],
                              pitch="Простой показывающий прибор для контроля давления."),
        clarifications=[],
    )
    data.update(overrides)
    return LLMDraft(**data)


@pytest.fixture
def manometer():
    return dict(MANOMETER)
