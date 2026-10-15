"""Shared set-up for the integration tests (Story 9.2).

`stack` builds Finnie's real services, the same way the app does, against the fake outside world in
support.py. Integration tests are offline by default: outside connections are watched and fail the
test, except to the Hugging Face hosts (the embedding model is downloaded once) and this machine.
Tests marked `live` are exempt, because they call real services on purpose.
"""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest
import respx
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.core.async_runner import AsyncRunner
from src.core.config import load_settings
from src.core.models import AgentRequest, SessionProfile
from src.rag.index import load_index, sentence_transformer_embedder
from src.rag.retriever import Retriever
from src.workflow import factory
from src.workflow.conversation import Conversation, plan_turn
from tests.integration.support import FakeAlphaVantage, FakeOpenAI, FakeSerpApi

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "src" / "web_app" / "app.py")
DIVERSIFIED_CSV = (ROOT / "src" / "data" / "samples" / "diversified.csv").read_bytes()
KEYS = {"OPENAI_API_KEY": "sk-test-openai-123456", "ALPHA_VANTAGE_API_KEY": "av-test-key-123456", "SERPAPI_API_KEY": "serp-test-key-123456"}
ALLOWED_SUFFIXES = ("huggingface.co", "hf.co", "cloudfront.net")  # where the embedding model comes from


def _allowed(host) -> bool:
    if host in ("localhost", None, "") or (isinstance(host, str) and host.startswith("/")):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return isinstance(host, str) and host.endswith(ALLOWED_SUFFIXES)


@pytest.fixture(autouse=True)
def network_attempts(request, monkeypatch):
    """Outside connections this test tried to make. Live tests are exempt; others fail if any are recorded."""
    attempts: list[str] = []
    if request.node.get_closest_marker("live"):
        yield attempts
        return
    real_connect, real_connect_ex, real_getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def connect(self, address):
        if isinstance(address, tuple) and not _allowed(address[0]):
            attempts.append(f"connect {address[0]}:{address[1]}")
            raise ConnectionRefusedError("outside connections are not allowed in integration tests")
        return real_connect(self, address)

    def connect_ex(self, address):
        if isinstance(address, tuple) and not _allowed(address[0]):
            attempts.append(f"connect {address[0]}:{address[1]}")
            return 111
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _allowed(host):
            attempts.append(f"lookup {host}")
            raise socket.gaierror("outside connections are not allowed in integration tests")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield attempts
    assert not attempts, f"this integration test tried to reach outside services: {attempts}"


@pytest.fixture(scope="session")
def retriever() -> Retriever:
    """The real knowledge-base search with the real embedding model, loaded once for the whole run."""
    settings = load_settings(environ=dict(KEYS))
    return Retriever(load_index(), sentence_transformer_embedder(), settings.rag.top_k, settings.rag.min_score)


class Stack(SimpleNamespace):
    """Finnie's real services plus the fake outside world, and helpers that work like the app does."""

    def ask(self, message: str, payload=None, profile: SessionProfile | None = None):
        request = AgentRequest(message=message, profile=profile or self.conversation.profile, payload=payload)
        return self.runner.run(self.services.workflow.run(request))

    def say(self, text: str, payload=None):
        """One chat turn exactly as the Chat tab does it: remember the answer in the conversation."""
        plan = plan_turn(self.conversation, text)
        response = plan.reply or self.runner.run(
            self.services.workflow.run(self.conversation.request(plan.message, self.settings.chat.history_turns, payload))
        )
        self.conversation.add(text, response, asked=plan.message)
        return response

    def run_agent(self, name, request: AgentRequest):
        return self.runner.run(self.services.agents[name].run(request))


@pytest.fixture
def stack(tmp_path, monkeypatch, retriever):
    openai_server = FakeOpenAI()
    alpha, serp = FakeAlphaVantage(), FakeSerpApi()
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("OPENAI_BASE_URL", openai_server.base_url)  # the real OpenAI client talks to the fake server
    # Plenty of request room and no spacing, so tests don't wait; the budgets themselves are the real ones.
    environ = {**KEYS, "OPENAI_BASE_URL": openai_server.base_url, "FINNIE_MARKET__PER_MINUTE_LIMIT": "100",
               "FINNIE_MARKET__MIN_INTERVAL_SECONDS": "0"}
    settings = load_settings(environ=environ)
    monkeypatch.setattr(factory, "create_retriever", lambda s: retriever)
    runner = AsyncRunner()
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        alpha.install(router)
        serp.install(router)
        services = factory.build_services(settings, cache_dir=tmp_path)
        services.llm.retry_base_seconds = 0  # retries without waiting
        yield Stack(
            services=services, settings=settings, openai=openai_server, alpha=alpha, serp=serp, runner=runner,
            conversation=Conversation(), cache_dir=tmp_path, router=router, environ=environ,
        )
    runner.close()
    openai_server.close()


@pytest.fixture
def app(stack, monkeypatch):
    """Streamlit AppTest wired to the integration `stack` (Story 9.2 dashboard tests, Story 9.3 UAT)."""
    monkeypatch.setattr(factory, "build_services", lambda settings: stack.services)
    st.cache_resource.clear()
    running = AppTest.from_file(APP, default_timeout=60)
    running.run()
    yield running
    st.cache_resource.clear()


def upload_portfolio(app, data=DIVERSIFIED_CSV):
    app.session_state["portfolio_input"] = ("mine.csv", data)
    app.run()
    return app
