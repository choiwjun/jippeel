"""고정 GPT OAuth provider 계약 테스트."""
from dataclasses import fields

import pytest

from app.services import gpt_oauth


def test_default_provider_is_local_and_fixed():
    provider = gpt_oauth.get_provider()

    assert provider.name == "ChatGPT OAuth"
    assert provider.base_url == "http://127.0.0.1:10531/v1"
    assert provider.default_model == "gpt-5.6-luna"
    assert provider.reasoning_effort == "xhigh"
    assert all(field.name != "temperature" for field in fields(provider))


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.invalid/v1",
        "http://192.0.2.1/v1",
        "http://127.0.0.1/chat",
        "http://127.0.0.1/v1/extra",
        "http://localhost/api/v1",
        "http://user@localhost/v1",
        "http://localhost/v1?redirect=remote",
        "http://localhost/v1#fragment",
        "http://[bad-host/v1",
    ],
)
def test_provider_rejects_non_bridge_urls(monkeypatch, base_url):
    monkeypatch.setenv("JIPPEEL_GPT_OAUTH_BASE_URL", base_url)

    with pytest.raises(gpt_oauth.OAuthProviderConfigError):
        gpt_oauth.get_provider()


def test_provider_rejects_unknown_reasoning_effort(monkeypatch):
    monkeypatch.setenv("JIPPEEL_GPT_REASONING_EFFORT", "turbo")

    with pytest.raises(gpt_oauth.OAuthProviderConfigError):
        gpt_oauth.get_provider()


def test_provider_allows_local_bridge_override_without_credentials(monkeypatch):
    monkeypatch.setenv("JIPPEEL_GPT_OAUTH_BASE_URL", "http://localhost:10531/v1/")
    monkeypatch.setenv("JIPPEEL_GPT_MODEL", "test-model")
    monkeypatch.setenv("JIPPEEL_GPT_REASONING_EFFORT", "high")

    provider = gpt_oauth.get_provider()

    assert provider.base_url == "http://localhost:10531/v1"
    assert provider.default_model == "test-model"
    assert provider.reasoning_effort == "high"
