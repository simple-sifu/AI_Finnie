"""Story 9.2 AC 4: an optional live smoke test with a small number of real API calls.

Off by default. It makes exactly ONE request to each real service (3 in all), so it barely touches the
free allowances (Alpha Vantage: 25 a day; SerpApi: about 100 a month). Run it with:

    RUN_LIVE_SMOKE=1 pytest -m live tests/integration/test_live_smoke.py -s

A service that answers "limit reached" still counts as reachable: the key was recognized and the
service responded, it just has no allowance left today. Any other failure (network, rejected key,
unexpected response) fails the test.
"""

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from src.core.config import load_settings
from src.core.llm import LLMClient
from src.core.market_data import AlphaVantageClient, PriceHistory, RateLimitError
from src.core.news import NewsLimitError, SerpApiClient
from src.workflow.router import ROUTER_PROMPT, RouteDecision

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.getenv("RUN_LIVE_SMOKE"), reason="set RUN_LIVE_SMOKE=1 to make one real request to each service"),
]
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def settings():
    load_dotenv(ROOT / ".env")
    return load_settings()


def run_once(settings):
    """One request to each real service, all on one event loop. Returns what each one said."""

    async def requests():
        outcome = {}
        llm = LLMClient.from_settings(settings)
        outcome["openai"] = await llm.structured(RouteDecision, ROUTER_PROMPT, "How is VTI doing today?")

        alpha = AlphaVantageClient.from_settings(settings)
        try:
            outcome["alpha_vantage"] = await alpha.get_daily_history("SPY")
        except RateLimitError as exc:
            outcome["alpha_vantage"] = exc
        finally:
            await alpha.aclose()

        serp = SerpApiClient(settings.secrets.serpapi_api_key.get_secret_value())
        try:
            outcome["serpapi"] = await serp.search("stock market")
        except NewsLimitError as exc:
            outcome["serpapi"] = exc
        finally:
            await serp.aclose()
        return outcome

    return asyncio.run(requests())


def test_each_real_service_answers_one_request(settings):
    outcome = run_once(settings)
    print()
    assert outcome["openai"].route == "market"  # OpenAI: the router understood the question
    for name in ("alpha_vantage", "serpapi"):
        value = outcome[name]
        reachable = "limit reached today, but the service answered" if isinstance(value, Exception) else "live data received"
        print(f"{name:14} {reachable}")
    assert isinstance(outcome["alpha_vantage"], (PriceHistory, RateLimitError))
    assert isinstance(outcome["serpapi"], (list, NewsLimitError))
    if isinstance(outcome["serpapi"], list):
        assert all(item.title and item.link for item in outcome["serpapi"])
