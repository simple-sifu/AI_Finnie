"""Story 8.1: Alpha Vantage client (HTTP mocked with respx; no real calls)."""

from datetime import date

import httpx
import pytest
import respx

from src.core.config import load_settings
from src.core.market_data import (
    BASE_URL,
    AlphaVantageClient,
    MarketDataError,
    NotFound,
    PriceHistory,
    Quote,
    RateLimitError,
    normalize_ticker,
)

QUOTE = {
    "Global Quote": {
        "01. symbol": "VTI",
        "02. open": "380.00",
        "05. price": "376.8800",
        "06. volume": "3262690",
        "07. latest trading day": "2026-10-14",
        "08. previous close": "381.3200",
        "09. change": "-4.4400",
        "10. change percent": "-1.1644%",
    }
}
HISTORY = {
    "Meta Data": {"2. Symbol": "VTI"},
    "Time Series (Daily)": {
        "2026-10-14": {"4. close": "376.88", "5. volume": "3262690"},
        "2026-10-13": {"4. close": "381.32", "5. volume": "2900000"},
        "2026-10-10": {"4. close": "379.05", "5. volume": "3100000"},
    },
}
LIMIT_NOTE = {"Note": "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day."}
BURST_INFO = {"Information": "Please consider spreading out your free API requests more sparingly (1 request per second)."}


@pytest.fixture
async def client():
    c = AlphaVantageClient("test-key")
    yield c
    await c.aclose()


def route(json=None, status=200):
    return respx.get(BASE_URL).mock(return_value=httpx.Response(status, json=json))


@respx.mock
async def test_quote_is_parsed(client):
    call = route(QUOTE)
    quote = await client.get_quote("vti")
    assert isinstance(quote, Quote)
    assert (quote.symbol, quote.price, quote.change, quote.change_percent) == ("VTI", 376.88, -4.44, -1.1644)
    assert quote.volume == 3262690 and quote.previous_close == 381.32
    assert quote.as_of == date(2026, 10, 14) and quote.fetched_at.tzinfo is not None
    params = call.calls.last.request.url.params
    assert params["function"] == "GLOBAL_QUOTE" and params["symbol"] == "VTI" and params["apikey"] == "test-key"


@respx.mock
async def test_history_is_parsed_oldest_first(client):
    call = route(HISTORY)
    history = await client.get_daily_history("VTI")
    assert isinstance(history, PriceHistory)
    assert [p.day for p in history.points] == [date(2026, 10, 10), date(2026, 10, 13), date(2026, 10, 14)]
    assert history.points[-1].close == 376.88 and history.as_of == date(2026, 10, 14)
    params = call.calls.last.request.url.params
    assert params["function"] == "TIME_SERIES_DAILY" and params["outputsize"] == "compact"


@respx.mock
async def test_unknown_ticker_quote_is_not_found(client):
    route({"Global Quote": {}})
    result = await client.get_quote("ZZZZZQ")
    assert result == NotFound("ZZZZZQ")
    assert "couldn't find that ticker" in result.message


@respx.mock
async def test_unknown_ticker_history_is_not_found(client):
    route({"Error Message": "Invalid API call. Please retry or visit the documentation."})
    assert await client.get_daily_history("ZZZZZQ") == NotFound("ZZZZZQ")


@respx.mock
async def test_empty_history_is_not_found(client):
    route({"Meta Data": {}, "Time Series (Daily)": {}})
    assert isinstance(await client.get_daily_history("VTI"), NotFound)


@pytest.mark.parametrize("bad", ["", "  ", "12AB", "TOO-LONG-TICKER", "$$$"])
@respx.mock
async def test_invalid_ticker_is_not_found_without_calling_the_api(client, bad):
    call = route(QUOTE)
    assert isinstance(await client.get_quote(bad), NotFound)
    assert isinstance(await client.get_daily_history(bad), NotFound)
    assert not call.called


@pytest.mark.parametrize("body", [LIMIT_NOTE, BURST_INFO])
@respx.mock
async def test_limit_notices_raise_rate_limit_error(client, body):
    route(body)
    with pytest.raises(RateLimitError):
        await client.get_quote("VTI")
    with pytest.raises(RateLimitError):
        await client.get_daily_history("VTI")


@respx.mock
async def test_server_error_raises_market_data_error(client):
    route({"error": "oops"}, status=503)
    with pytest.raises(MarketDataError, match="HTTP 503"):
        await client.get_quote("VTI")


@respx.mock
async def test_network_error_raises_market_data_error(client):
    respx.get(BASE_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(MarketDataError, match="ConnectTimeout"):
        await client.get_quote("VTI")


@respx.mock
async def test_non_json_response_raises_market_data_error(client):
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, text="<html>maintenance</html>"))
    with pytest.raises(MarketDataError):
        await client.get_quote("VTI")


@respx.mock
async def test_non_object_json_raises_market_data_error(client):
    route(["unexpected"])
    with pytest.raises(MarketDataError, match="unexpected response"):
        await client.get_quote("VTI")


@respx.mock
async def test_malformed_quote_raises_market_data_error(client):
    route({"Global Quote": {"05. price": "not-a-number"}})
    with pytest.raises(MarketDataError, match="Unexpected quote format"):
        await client.get_quote("VTI")


@respx.mock
async def test_malformed_history_raises_market_data_error(client):
    route({"Time Series (Daily)": {"2026-10-14": {"4. close": "abc"}}})
    with pytest.raises(MarketDataError, match="Unexpected price history format"):
        await client.get_daily_history("VTI")


@respx.mock
async def test_api_key_never_appears_in_errors(client):
    route({"error": "oops"}, status=500)
    with pytest.raises(MarketDataError) as error:
        await client.get_quote("VTI")
    assert "test-key" not in str(error.value)


@respx.mock
async def test_client_from_settings_uses_the_configured_key(tmp_path):
    settings = load_settings(
        config_path=tmp_path / "none.yaml",
        environ={"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "from-config", "SERPAPI_API_KEY": "s"},
    )
    call = route(QUOTE)
    client = AlphaVantageClient.from_settings(settings)
    await client.get_quote("VTI")
    await client.aclose()
    assert call.calls.last.request.url.params["apikey"] == "from-config"


def test_normalize_ticker():
    assert normalize_ticker(" brk.b ") == "BRK.B"
    assert normalize_ticker("vti") == "VTI"
    assert normalize_ticker("1ABC") is None and normalize_ticker(None) is None


def test_markets_tab_tickers_are_configured():
    settings = load_settings(
        environ={"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}
    )
    assert 3 <= len(settings.market.tickers) <= 5
