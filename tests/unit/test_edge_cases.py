"""Story 9.1 AC 3: edge cases. Malformed queries and uploads, API limit responses, and malformed API responses.

Random inputs use fixed seeds, so every run is the same and any failure can be reproduced.
"""

import asyncio
import math
import random
import re
import string

import httpx
import openai
import pytest
import respx

from src.agents.base import AGENT_FAILED, LLMAnswer
from src.agents.goal_planning import GoalExtraction
from src.agents.market import explicit_tickers
from src.agents.tax import strip_unsupported, unsupported_figures
from src.core.calculators import price_changes, plan_goal, required_monthly_saving
from src.core.config import ConfigError, load_settings
from src.core.holdings import parse_holdings
from src.core.llm import LLMClient, LLMUnavailableError
from src.core.market_data import BASE_URL, AlphaVantageClient, MarketDataError, NotFound, RateLimitError, normalize_ticker
from src.core.models import AgentName, AgentRequest, ChatTurn
from src.core.news import SERPAPI_URL, NewsError, NewsLimitError, SerpApiClient, normalize_query, parse_results
from src.rag.chunking import chunk_article
from src.rag.content import Article
from src.workflow.conversation import parse_risk_tolerance
from tests.unit.test_error_fallbacks import flow as error_flow

KEYS = {"OPENAI_API_KEY": "sk-test-openai-123456", "ALPHA_VANTAGE_API_KEY": "av-test-key-123456", "SERPAPI_API_KEY": "serp-test-key-123456"}
NASTY = list(string.printable) + list("éñüß中文日本語한국어العربيةעברית​‎‮﻿\x00\x07\x1b😀🚀") + ["ticker", "shares", "expense_ratio", "VTI", "nan", "inf", "1e400", "-0", "'; DROP TABLE x; --", "<script>"]


def random_text(rng, max_len=200):
    return "".join(rng.choice(NASTY) for _ in range(rng.randrange(0, max_len)))


# --- malformed uploads --------------------------------------------------------------------------------------


def assert_sane(result):
    assert isinstance(result.problems, list) and all(isinstance(p, str) and p.strip() for p in result.problems)
    if result.ok:
        assert result.holdings and not result.problems
        for holding in result.holdings:
            assert re.fullmatch(r"[A-Z][A-Z.\-]{0,9}", holding.ticker)
            assert math.isfinite(holding.shares) and holding.shares > 0
            assert holding.expense_ratio is None or 0 <= holding.expense_ratio < 3
    else:
        assert result.holdings == []  # no analysis from a bad file


@pytest.mark.parametrize("seed", range(300))
def test_the_holdings_parser_never_raises_on_random_bytes_or_text(seed):
    rng = random.Random(seed)
    data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 400))) if seed % 2 else random_text(rng).encode("utf-8", "ignore")
    assert_sane(parse_holdings(data))


@pytest.mark.parametrize("seed", range(150))
def test_a_valid_header_with_random_rows_gives_a_sane_result(seed):
    rng = random.Random(1000 + seed)
    rows = "\n".join(",".join(random_text(rng, 12) for _ in range(rng.randrange(1, 5))) for _ in range(rng.randrange(0, 8)))
    assert_sane(parse_holdings(f"ticker,shares,expense_ratio\n{rows}\n"))


@pytest.mark.parametrize(
    "data, expectation",
    [
        ("ticker;shares\nVTI;5\n", "needs a 'ticker' and a 'shares' column"),  # semicolons, as some spreadsheets save
        ("ticker\tshares\nVTI\t5\n", "needs a 'ticker' and a 'shares' column"),  # tab separated
        ("ticker,shares\r\nVTI,5\r\n", "ok"),  # Windows line endings
        ("﻿ticker,shares\r\nVTI,5\r\n", "ok"),  # byte-order mark and Windows endings
        ('"ticker","shares"\n"VTI","5"\n', "ok"),  # everything quoted
        ("ticker,shares,\nVTI,5,\n", "ok"),  # a trailing comma
        ("ticker,shares,notes,more\nVTI,5,hello,there\n", "ok"),  # extra columns
        ("ticker,shares\nvti,5\n", "ok"),  # lowercase
        ("ticker,shares\nVTI,1e3\n", "ok"),  # scientific notation is a number
        ("ticker,shares\nVTI,1e400\n", "shares is not a number"),  # too big to be a number
        ("ticker,shares\nVTI,-0\n", "shares must be more than 0"),
        ("ticker,shares\nV TI,5\n", "isn't a valid US ticker"),  # a space inside the ticker
        ("ticker,shares\n\n\n", "no holdings"),
        ("ticker,ticker,shares\nVTI,BND,5\n", "ok"),  # a repeated header name
        ("ticker,shares\n" + "VTI,1\n" * 3 + ",\n,,\n", "ok"),  # blank rows are skipped
    ],
)
def test_common_malformed_uploads_get_a_clear_answer(data, expectation):
    result = parse_holdings(data)
    assert_sane(result)
    if expectation == "ok":
        assert result.ok
    else:
        assert not result.ok and expectation in " ".join(result.problems)


def test_a_single_enormous_field_is_a_problem_not_a_crash():
    result = parse_holdings(b"ticker,shares\n" + b"A" * 200_000 + b",5\n")  # beyond Python's csv field limit
    assert not result.ok and result.holdings == [] and result.problems


# --- malformed queries through the whole workflow ------------------------------------------------------------


@pytest.mark.parametrize("seed", range(120))
def test_random_messages_always_get_an_answer_and_never_raise(seed):
    rng = random.Random(5000 + seed)
    response = asyncio.run(error_flow(max_chars=100).run(AgentRequest(message=random_text(rng, 150))))
    assert response.answer.strip()


@pytest.mark.parametrize(
    "message",
    ["​​​", "‮‮", "   \n\n\t  ", "a" * 99, "é" * 99, "🚀" * 40, "ñandú 你好 مرحبا שלום", "?", "<<<>>>", "%s %d {0} {name}", "\\n\\t"],
)
def test_unusual_messages_are_handled(message):
    assert asyncio.run(error_flow(max_chars=100).run(AgentRequest(message=message))).answer.strip()


@pytest.mark.parametrize("seed", range(80))
def test_text_helpers_never_raise_on_random_text(seed):
    text = random_text(random.Random(9000 + seed), 300)
    assert normalize_ticker(text) is None or re.fullmatch(r"[A-Z][A-Z.\-]{0,9}", normalize_ticker(text))
    assert isinstance(normalize_query(text), str) and parse_risk_tolerance(text) in (None, "conservative", "moderate", "aggressive")
    assert len(explicit_tickers(text)) <= 3
    assert isinstance(unsupported_figures(text, text), list)
    stripped, removed = strip_unsupported(text, "")
    assert isinstance(stripped, str) and removed >= 0
    assert isinstance(price_changes([abs(hash(c)) % 100 for c in text]), dict)


@pytest.mark.parametrize("seed", range(150))
def test_chunking_random_markdown_never_makes_empty_or_oversized_chunks(seed):
    rng = random.Random(7000 + seed)
    pieces = ["## " + random_text(rng, 20), random_text(rng, 400), "", "# " + random_text(rng, 10), "x" * rng.choice([0, 50, 5000])]
    body = "\n\n".join(rng.choice(pieces) for _ in range(rng.randrange(0, 12)))
    article = Article("a", "Title", "Stocks", "Src", "https://x/", body)
    size = rng.choice([200, 400, 800])
    for chunk in chunk_article(article, size, rng.choice([0, 20, 100])):
        assert chunk.text.strip() and len(chunk.text) <= size


def test_a_word_longer_than_a_whole_chunk_is_split_without_looping_forever():
    article = Article("a", "T", "Stocks", "S", "https://x/", "## Long\n\n" + "w" * 5000)
    chunks = chunk_article(article, 300, 50)
    assert len(chunks) > 10 and all(len(c.text) <= 300 for c in chunks)


# --- calculations at the extremes -----------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(60))
def test_random_goals_reach_the_target_by_simulation_and_never_give_nan_or_inf(seed):
    rng = random.Random(3000 + seed)
    target = rng.choice([1.0, 500.0, 20_000.0, 1_000_000.0, 1_000_000_000.0])
    current = rng.choice([0.0, target * rng.random()])
    months = rng.choice([1, 2, 11, 12, 13, 120, 360, 720])
    rate = rng.choice([0.0, 0.01, 0.03, 0.05, 0.07, 0.12])
    monthly = required_monthly_saving(target, current, months, rate)
    assert math.isfinite(monthly) and monthly >= 0
    r = (1 + rate) ** (1 / 12) - 1
    balance = current
    for _ in range(months):
        balance = balance * (1 + r) + monthly
    assert balance >= target - 0.005 * months  # reached, allowing for floating-point rounding per month
    plan = plan_goal(target, current, months, rate)
    assert all(math.isfinite(b) for _, b in plan.schedule) and plan.schedule[-1][0] == months


# --- API limit responses ----------------------------------------------------------------------------------------


@pytest.fixture
async def alpha():
    client = AlphaVantageClient("test-key")
    yield client
    await client.aclose()


@pytest.fixture
async def serp():
    client = SerpApiClient("serp-key")
    yield client
    await client.aclose()


@respx.mock
async def test_alpha_vantage_http_429_is_a_limit_not_a_retryable_failure(alpha):
    respx.get(BASE_URL).mock(return_value=httpx.Response(429, text="Too Many Requests"))
    with pytest.raises(RateLimitError):
        await alpha.get_quote("VTI")


@respx.mock
async def test_serpapi_http_429_is_a_limit(serp):
    respx.get(SERPAPI_URL).mock(return_value=httpx.Response(429, json={"error": "Too many requests"}))
    with pytest.raises(NewsLimitError):
        await serp.search("stock market")


@pytest.mark.parametrize("error", [openai.RateLimitError, openai.InternalServerError])
def test_openai_rate_limit_and_server_errors_are_retried_then_succeed(error):
    response = httpx.Response(429 if error is openai.RateLimitError else 500, request=httpx.Request("POST", "https://api.openai.com/v1/x"))

    class Model:
        calls = 0

        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, messages):
            Model.calls += 1
            if Model.calls < 3:
                raise error("busy", response=response, body=None)
            return LLMAnswer(answer="ok", response_type="education")

    result = asyncio.run(LLMClient(Model(), max_retries=3, retry_base_seconds=0).structured(LLMAnswer, "s", "u"))
    assert result.answer == "ok" and Model.calls == 3


def test_openai_timeouts_exhaust_into_unavailable_and_an_agent_reports_it_kindly():
    class Model:
        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, messages):
            raise openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/x"))

    client = LLMClient(Model(), max_retries=1, retry_base_seconds=0)
    with pytest.raises(LLMUnavailableError):
        asyncio.run(client.structured(LLMAnswer, "s", "u"))


def test_an_openai_key_problem_is_not_retried_and_the_agent_answers_kindly():
    from src.agents.market import MarketAgent
    from tests.unit.test_market_agent import FakeMarket

    response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1/x"))

    class Model:
        calls = 0

        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, messages):
            Model.calls += 1
            raise openai.AuthenticationError("bad key", response=response, body=None)

    agent = MarketAgent(LLMClient(Model(), max_retries=3, retry_base_seconds=0), "d", FakeMarket())
    answer = asyncio.run(agent.run(AgentRequest(message="Tell me about that thing")))  # no ticker: needs the LLM to look one up
    assert Model.calls == 1 and answer.answer == AGENT_FAILED and answer.error and "bad key" not in answer.answer


# --- malformed API responses ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"Time Series (Daily)": {"2026-10-14": "not an object"}},
        {"Time Series (Daily)": {"2026-10-14": None}},
        {"Time Series (Daily)": {"2026-10-14": ["4. close"]}},
        {"Time Series (Daily)": ["a", "list"]},
        {"Time Series (Daily)": "text"},
        {"Time Series (Daily)": {"not a date": {"4. close": "1", "5. volume": "1"}}},
    ],
)
@respx.mock
async def test_malformed_price_history_is_an_error_the_fallbacks_can_handle(alpha, payload):
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(MarketDataError):
        await alpha.get_daily_history("VTI")


@pytest.mark.parametrize("payload", [{"Global Quote": ["a"]}, {"Global Quote": "text"}, {"Global Quote": {"05. price": None}}])
@respx.mock
async def test_malformed_quotes_are_errors_or_not_found_never_crashes(alpha, payload):
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=payload))
    try:
        result = await alpha.get_quote("VTI")
    except MarketDataError:
        return
    assert isinstance(result, NotFound)


@pytest.mark.parametrize(
    "data",
    [
        {"news_results": 5}, {"news_results": "text"}, {"news_results": ["a", None, 3]}, {"news_results": [{"stories": "text"}]},
        {"news_results": [{"title": 5, "link": ["x"]}]}, {"news_results": [{"stories": [None, 5, {"title": "T", "link": "https://x/1"}]}]},
        {"news_results": [{"title": "T", "link": "https://x/2", "source": 42, "iso_date": 12345}]}, {},
    ],
)
def test_malformed_news_results_are_skipped_not_crashed_on(data):
    items = parse_results(data)
    assert all(i.title and i.link for i in items)
    assert len(items) <= 1


@respx.mock
async def test_serpapi_with_a_weird_body_is_an_error_the_fallbacks_can_handle(serp):
    respx.get(SERPAPI_URL).mock(return_value=httpx.Response(200, json={"news_results": 5}))
    assert await serp.search("x") == []  # nothing usable, and no crash


def test_malformed_goal_extraction_is_just_missing_information():
    from src.agents.goal_planning import GoalPlanningAgent

    class WeirdLLM:
        async def structured(self, schema, system, user, history=None):
            if schema is GoalExtraction:
                return GoalExtraction(target_amount=None, years=None, target_date="31/12/2030", current_savings=None)
            return LLMAnswer(answer="x", response_type="advice")

    from src.core.models import SessionProfile

    agent = GoalPlanningAgent(WeirdLLM(), "d", {"moderate": 0.05})
    response = asyncio.run(agent.run(AgentRequest(message="plan", profile=SessionProfile(risk_tolerance="moderate"))))
    assert response.needs_input == "goal_details" and not response.error  # an unreadable date counts as missing


# --- bad settings ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra, field",
    [
        ({"QUOTE_CACHE_TTL_SECONDS": "abc"}, "market.quote_ttl_seconds"),
        ({"QUOTE_CACHE_TTL_SECONDS": "-5"}, "market.quote_ttl_seconds"),
        ({"MARKET_DATA_MODE": "maybe"}, "market.mode"),
        ({"FINNIE_CHAT__HISTORY_TURNS": "0"}, "chat.history_turns"),
        ({"FINNIE_ROUTER__MIN_CONFIDENCE": "7"}, "router.min_confidence"),
        ({"FINNIE_LOGGING__LEVEL": "LOUD"}, "logging.level"),
    ],
)
def test_junk_in_settings_gives_a_readable_error_naming_the_setting(tmp_path, extra, field):
    with pytest.raises(ConfigError) as error:
        load_settings(config_path=tmp_path / "none.yaml", environ={**KEYS, **extra})
    assert field in str(error.value) and not any(key in str(error.value) for key in KEYS.values())
