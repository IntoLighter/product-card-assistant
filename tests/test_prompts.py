from app.core.models import Issue
from app.core.profiles import detect_profile
from app.core.prompts import build_fix_messages, build_messages, system_prompt, user_prompt
from app.core.validation import normalize_product
from tests.factories import manometer


def test_system_prompt_has_limits_and_no_placeholders():
    prompt = system_prompt()
    assert "$" not in prompt
    assert "не длиннее 70 символов" in prompt
    assert "от 800 до 1200 символов" in prompt


def test_user_prompt_contains_data_and_missing_fields():
    raw = manometer()
    raw["manufacturer"] = None
    product = normalize_product(raw).product

    prompt = user_prompt(product, detect_profile(product), ["Измеряемая среда"])

    assert '"класс точности": "1,5"' in prompt
    assert '"производитель": "данных нет"' in prompt
    assert "- Измеряемая среда" in prompt
    assert "$" not in prompt


def test_fix_messages_extend_conversation():
    product = normalize_product(manometer()).product
    messages = build_messages(product, detect_profile(product), [])

    fixed = build_fix_messages(messages, '{"seo_title": "..."}', [Issue(field="seo_title", message="Слишком длинно.")])

    assert fixed[: len(messages)] == messages
    assert fixed[-2] == {"role": "assistant", "content": '{"seo_title": "..."}'}
    assert "- Слишком длинно." in str(fixed[-1]["content"])
