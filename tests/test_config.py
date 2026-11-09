import pytest
from pydantic import ValidationError

from core.config import Settings

ENV = {
    "LLM_BASE_URL": "http://vllm:8000/v1",
    "LLM_MODEL": "local-model",
    "LLM_API_KEY": "EMPTY",
    "TEMPERATURE": "0.3",
    "SEED": "42",
    "REQUEST_TIMEOUT": "120",
    "MAX_ATTEMPTS": "3",
}


@pytest.fixture
def env(monkeypatch):
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_defaults_come_from_dotenv():
    settings = Settings()

    assert settings.model == "local-model"
    assert settings.max_attempts >= 1


def test_environment_overrides_dotenv(env):
    env.setenv("LLM_BASE_URL", "http://other:9000/v1")

    assert Settings().base_url == "http://other:9000/v1"


def test_values_are_parsed(env):
    settings = Settings(_env_file=None)

    assert settings.temperature == 0.3
    assert settings.seed == 42
    assert settings.timeout == 120.0


def test_missing_variable_is_reported(env):
    env.delenv("LLM_MODEL")

    with pytest.raises(ValidationError, match="LLM_MODEL"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("name", "value"),
    [("SEED", "abc"), ("MAX_ATTEMPTS", "0"), ("REQUEST_TIMEOUT", "-1")],
    ids=["seed-not-number", "attempts-zero", "timeout-negative"],
)
def test_invalid_value_is_reported(env, name, value):
    env.setenv(name, value)

    with pytest.raises(ValidationError, match=name):
        Settings(_env_file=None)
