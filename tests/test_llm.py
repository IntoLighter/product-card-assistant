import httpx2
import openai
import pytest
from openai.types.chat import ChatCompletion

from app.core.config import Settings
from app.core.llm import LLMOutputError, describe_api_error, parse_response
from app.core.models import LLMDraft
from tests.factories import make_draft

SETTINGS = Settings(base_url="http://vllm:8000/v1", model="local-model")
REQUEST = httpx2.Request("POST", "http://vllm:8000/v1/chat/completions")


def completion(content, finish_reason="stop", *, choices=True):
    choice = {"index": 0, "finish_reason": finish_reason, "message": {"role": "assistant", "content": content}}
    return ChatCompletion.model_validate(
        {"id": "1", "object": "chat.completion", "created": 0, "model": "m", "choices": [choice] if choices else []}
    )


def test_valid_response_parsed():
    draft = make_draft()
    assert parse_response(completion(draft.model_dump_json()), LLMDraft) == draft


@pytest.mark.parametrize(
    "response",
    [
        completion("не JSON"),
        completion('{"seo_title": "без остальных полей"}'),
        completion(make_draft().model_dump_json(), finish_reason="length"),
        completion(None, choices=False),
    ],
    ids=["not-json", "schema-mismatch", "truncated", "no-choices"],
)
def test_invalid_response_raises_output_error(response):
    with pytest.raises(LLMOutputError):
        parse_response(response, LLMDraft)


def status_error(error_class, status_code):
    response = httpx2.Response(status_code, request=REQUEST)
    return error_class("error", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "hint"),
    [
        (openai.APIConnectionError(request=REQUEST), "docker compose ps"),
        (openai.APITimeoutError(request=REQUEST), "REQUEST_TIMEOUT"),
        (status_error(openai.NotFoundError, 404), "LLM_MODEL"),
        (status_error(openai.AuthenticationError, 401), "LLM_API_KEY"),
        (status_error(openai.InternalServerError, 500), "HTTP 500"),
    ],
    ids=["connection", "timeout", "not-found", "auth", "server"],
)
def test_api_errors_explained(error, hint):
    assert hint in describe_api_error(error, SETTINGS)
