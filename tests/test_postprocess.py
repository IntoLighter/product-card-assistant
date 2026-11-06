from core.postprocess import fit_description, fit_draft
from factories import make_draft

# 79 символов
SENTENCE = (
    "Прибор показывает избыточное давление на месте установки и не требует питания."
)


def paragraphs(count, sentences_each):
    return "\n\n".join(" ".join([SENTENCE] * sentences_each) for _ in range(count))


def test_short_enough_text_unchanged():
    text = paragraphs(4, 3)  # ~950 символов
    assert fit_description(text) == text


def test_long_text_trimmed_by_whole_sentences():
    text = paragraphs(4, 5)  # ~1600 символов
    fitted = fit_description(text)
    assert 800 <= len(fitted) <= 1200
    assert fitted.endswith(SENTENCE)
    assert text.startswith(fitted[:500])


def test_empty_paragraph_removed_after_trim():
    text = paragraphs(3, 4) + "\n\n" + SENTENCE  # последний абзац из одного предложения
    fitted = fit_description(text)
    assert "\n\n\n" not in fitted
    assert not fitted.endswith("\n")


def test_not_trimmed_below_minimum():
    one_long_sentence = "Слово " * 250 + "конец."
    assert fit_description(one_long_sentence) == one_long_sentence


def test_fit_draft_replaces_only_description():
    draft = make_draft(seo_description=paragraphs(4, 5))
    fitted = fit_draft(draft)
    assert len(fitted.seo_description) <= 1200
    assert fitted.seo_title == draft.seo_title
    assert fit_draft(make_draft()) == make_draft()
