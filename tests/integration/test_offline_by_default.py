"""Story 9.2 AC 3: integration tests run with mocked external APIs by default."""

import pytest

from src.core.llm import LLMClient, LLMUnavailableError
from src.workflow.router import ROUTER_PROMPT, RouteDecision
from tests.integration.conftest import _allowed


def test_only_this_machine_and_the_model_download_hosts_are_allowed():
    for host in ("127.0.0.1", "localhost", "::1", "huggingface.co", "cdn-lfs.huggingface.co", "xethub.hf.co"):
        assert _allowed(host), host
    for host in ("api.openai.com", "www.alphavantage.co", "serpapi.com", "example.com", "8.8.8.8"):
        assert not _allowed(host), host


def test_the_real_openai_client_cannot_reach_openai_unless_a_fake_server_is_configured(monkeypatch, network_attempts):
    from src.core.config import load_settings
    from tests.integration.conftest import KEYS

    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)  # no fake server: the client would go to api.openai.com
    client = LLMClient.from_settings(load_settings(environ=dict(KEYS)))
    client.max_retries, client.retry_base_seconds = 0, 0
    with pytest.raises(LLMUnavailableError):
        import asyncio

        asyncio.run(client.structured(RouteDecision, ROUTER_PROMPT, "hello"))
    assert any("api.openai.com" in attempt for attempt in network_attempts)  # it tried, and was stopped
    network_attempts.clear()  # this test did it on purpose


def test_the_stack_talks_only_to_the_fake_services(stack, network_attempts):
    stack.ask("How is VTI doing?")
    stack.ask("What's in the financial news today?")
    stack.ask("What is compound interest?")
    assert stack.alpha.calls and stack.serp.queries and stack.openai.calls  # all three fakes were used
    assert network_attempts == []  # and nothing else was reached
