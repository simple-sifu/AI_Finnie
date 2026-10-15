"""A fake outside world for the integration tests (Story 9.2).

The tests run Finnie's real code from the workflow down to the HTTP calls: the router, the agents, the
real knowledge-base search with the real embedding model, the real data clients, caches and request
budgets, and the real OpenAI client library. Only the three outside services are faked:

- FakeOpenAI: a small web server on this machine. The real OpenAI client is pointed at it with the
  standard OPENAI_BASE_URL setting. Its replies are rule-based and read the real prompts, so the tests
  can show that retrieved content, prices and calculations really reach the model.
- FakeAlphaVantage and FakeSerpApi: HTTP-level fakes installed with respx.

Replies are deterministic. Nothing here costs money or uses an API allowance.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from src.core.market_data import BASE_URL as ALPHA_VANTAGE_URL
from src.core.news import SERPAPI_URL

LAST_DAY = date(2026, 10, 14)  # the latest trading day in the fake market data

# --- Alpha Vantage ------------------------------------------------------------------------------------------

# symbol -> (previous close, last close). The days before are a gentle climb to the previous close.
PRICES = {
    "VTI": (381.32, 376.88), "SPY": (778.01, 769.60), "QQQ": (743.57, 728.95), "DIA": (473.10, 470.00),
    "BND": (74.35, 74.20), "VXUS": (73.40, 72.50), "VNQ": (93.60, 92.80), "AAPL": (258.90, 255.00),
    "TSLA": (441.50, 430.00), "VOO": (714.80, 707.00), "MSFT": (519.80, 515.00), "SCHB": (27.40, 27.10),
}
LIMIT_NOTE = "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day."


def _bars(symbol: str) -> dict:
    prev, last = PRICES[symbol]
    closes = [round(prev * (0.9 + 0.1 * i / 98), 2) for i in range(99)] + [last]
    closes[-2] = prev
    return {
        (LAST_DAY - timedelta(days=len(closes) - 1 - i)).isoformat():
            {"1. open": str(c), "2. high": str(c), "3. low": str(c), "4. close": str(c), "5. volume": "1000000"}
        for i, c in enumerate(closes)
    }


class FakeAlphaVantage:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []  # (function, symbol)
        self.limit_after: int | None = None  # after this many requests, answer with the daily-limit notice

    def handler(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        function, symbol = params["function"], params["symbol"]
        self.calls.append((function, symbol))
        if self.limit_after is not None and len(self.calls) > self.limit_after:
            return httpx.Response(200, json={"Note": LIMIT_NOTE})
        if symbol not in PRICES:
            return httpx.Response(200, json={"Global Quote": {}} if function == "GLOBAL_QUOTE" else {"Error Message": "Invalid API call."})
        prev, last = PRICES[symbol]
        if function == "GLOBAL_QUOTE":
            return httpx.Response(200, json={"Global Quote": {
                "01. symbol": symbol, "05. price": f"{last:.4f}", "06. volume": "1000000", "07. latest trading day": LAST_DAY.isoformat(),
                "08. previous close": f"{prev:.4f}", "09. change": f"{last - prev:.4f}", "10. change percent": f"{(last / prev - 1) * 100:.4f}%",
            }})
        return httpx.Response(200, json={"Meta Data": {"2. Symbol": symbol}, "Time Series (Daily)": _bars(symbol)})

    def install(self, router) -> None:
        router.get(ALPHA_VANTAGE_URL).mock(side_effect=self.handler)

    def requests_for(self, function: str) -> list[str]:
        return [symbol for fn, symbol in self.calls if fn == function]


# --- SerpApi ------------------------------------------------------------------------------------------------


class FakeSerpApi:
    def __init__(self):
        self.queries: list[str] = []
        self.out_of_searches = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        self.queries.append(query)
        if self.out_of_searches:
            return httpx.Response(429, json={"error": "Your account has run out of searches."})
        topic = query.title()
        articles = [
            ("Reuters", f"{topic}: stocks slip as investors weigh new inflation data", "https://news.example/reuters/1"),
            ("Bloomberg.com", f"{topic}: bond yields rise ahead of the Fed decision", "https://news.example/bloomberg/2"),
            ("CNBC", f"{topic}: what traders are watching this week", "https://news.example/cnbc/3"),
        ]
        return httpx.Response(200, json={"news_results": [
            {"title": title, "link": link, "source": {"name": publisher}, "iso_date": f"{LAST_DAY.isoformat()}T20:00:00Z"}
            for publisher, title, link in articles
        ]})

    def install(self, router) -> None:
        router.get(SERPAPI_URL).mock(side_effect=self.handler)


# --- OpenAI -------------------------------------------------------------------------------------------------


@dataclass
class Call:
    """One request the real OpenAI client made to the fake server."""

    schema: str  # the name of the structured answer asked for, e.g. "RouteDecision"
    system: str
    user: str
    history: list[tuple[str, str]] = field(default_factory=list)  # earlier (role, text) messages


KNOWN_TICKERS = set(PRICES)
COMPANIES = {"apple": "AAPL", "tesla": "TSLA", "microsoft": "MSFT", "vanguard total stock": "VTI"}


def _first_passage(system: str) -> tuple[str, str] | None:
    """(title, first sentence) of the first retrieved passage, as the agent put it in the prompt."""
    match = re.search(r"\[1\] ([^\n]*)\n(.*?)(?:\n\n---\n\n|\n\nAnswer ONLY|$)", system, re.S)
    if not match:
        return None
    title = re.sub(r"\s*\(figures are for \d{4}\)$", "", match.group(1)).strip()
    body = match.group(2).split("\n\n", 1)[-1]  # the chunk text starts with the title and a blank line
    sentence = re.split(r"(?<=[.!?])\s", body.strip(), maxsplit=1)[0]
    return title, sentence


class ScriptedModel:
    """Rule-based stand-in for the language model. It reads the real prompts and answers from them."""

    def route(self, call: Call) -> dict:
        text, previous = call.user.lower(), re.search(r"agent \((\w+)\)", call.system)
        words = set(re.findall(r"[a-z0-9()$]+", text))
        tickers = {t for t in re.findall(r"\b[A-Z]{2,5}\b", call.user) if t in KNOWN_TICKERS}
        if any(w in text for w in ("pizza", "weather", "recipe")):
            route = "off_topic"
        elif any(w in text for w in ("portfolio", "holdings")):
            route = "portfolio"
        elif "$" in text and ("year" in text or "save" in text):
            route = "goal_planning"
        elif "news" in text or "headline" in text:
            route = "news"
        elif any(w in text for w in ("401(k)", "401k", "ira", "roth", "hsa", "capital gain", "tax")):
            route = "tax"
        elif tickers or "stock price" in text or "how is" in text:
            route = "market"
        elif previous and len(words) <= 5:
            route = previous.group(1)  # a short follow-up stays with the agent that answered last
        else:
            route = "finance_qa"
        return {"route": route, "confidence": 0.9, "clarifying_question": None}

    def grounded(self, call: Call) -> dict:
        passage = _first_passage(call.system)
        if passage is None:
            return {"answer": "I don't know.", "response_type": "education", "answered_from_content": False}
        title, sentence = passage
        advice = bool(re.search(r"\b(should|better|choose)\b", call.user.lower()))
        return {"answer": f"From {title}: {sentence}", "response_type": "advice" if advice else "education",
                "answered_from_content": True, "non_us": False}

    def portfolio(self, call: Call) -> dict:
        total = re.search(r"Total value: (\$[\d,]+\.\d\d)", call.system)
        flagged = "Single stocks over 20%" in call.system
        return {"answer": f"Your portfolio is worth {total.group(1) if total else 'an unknown amount'}.",
                "response_type": "education", "includes_recommendation": flagged}

    def explanation(self, call: Call) -> dict:
        saving = re.search(r"Required saving: (\$[\d,]+\.\d\d) per month", call.system)
        quote = re.search(r"([A-Z.]{2,6}): price (\$[\d,]+\.\d\d)", call.system)
        if "Savings plan:" in call.system:
            answer = f"To reach your goal, save about {saving.group(1)} a month." if saving else "Your savings already cover this goal."
        elif quote:
            answer = f"{quote.group(1)} closed at {quote.group(2)}."
        else:
            answer = "Here is a short explanation."
        advice = bool(re.search(r"\b(buy|sell)\b", call.user.lower()))
        return {"answer": answer, "response_type": "advice" if advice else "education"}

    def tickers(self, call: Call) -> dict:
        text = call.user.lower()
        found = [symbol for name, symbol in COMPANIES.items() if name in text]
        return {"tickers": found, "overall_market": "market" in text and not found}

    def goal(self, call: Call) -> dict:
        said = " ".join([t for role, t in call.history if role == "user"] + [call.user])
        amounts = [float(n.replace(",", "")) * (1000 if k else 1) for n, k in re.findall(r"\$\s?([\d,]+(?:\.\d+)?)(k?)", said)]
        saved = re.search(r"(?:have|saved|already)[^$]*\$\s?([\d,]+)", said)
        years = re.search(r"in (\d+(?:\.\d+)?) years?", said)
        target = amounts[0] if amounts else None
        return {"target_amount": target, "years": float(years.group(1)) if years else None, "target_date": None,
                "current_savings": float(saved.group(1).replace(",", "")) if saved else (0.0 if "nothing saved" in said else None)}

    def news_query(self, call: Call) -> dict:
        text = call.user.lower()
        query = "Federal Reserve interest rates" if ("fed" in text or "rate" in text) else "inflation" if "inflation" in text else "stock market"
        return {"query": query}

    def news_summary(self, call: Call) -> dict:
        first = re.search(r"1\. (.*?) \(([^,)]+)", call.system)
        answer = f"According to {first.group(2)}, {first.group(1)}" if first else "No details."
        return {"answer": answer, "response_type": "education", "relevant": bool(first), "used": [1]}

    def answer(self, call: Call) -> dict | None:
        handlers = {
            "RouteDecision": self.route, "GroundedAnswer": self.grounded, "TaxAnswer": self.grounded,
            "PortfolioExplanation": self.portfolio, "LLMAnswer": self.explanation, "TickerRequest": self.tickers,
            "GoalExtraction": self.goal, "NewsQuery": self.news_query, "NewsSummary": self.news_summary,
        }
        return handlers[call.schema](call)


class FakeOpenAI:
    """A web server on this machine that speaks just enough of OpenAI's chat API for structured answers."""

    def __init__(self, model: ScriptedModel | None = None):
        self.model = model or ScriptedModel()
        self.calls: list[Call] = []
        self.failures: list[int] = []  # HTTP statuses to return for the next requests, one each
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                messages = [(m["role"], m["content"] if isinstance(m["content"], str) else "") for m in body["messages"]]
                call = Call(
                    schema=body["response_format"]["json_schema"]["name"],
                    system=next((text for role, text in messages if role in ("system", "developer")), ""),
                    user=messages[-1][1],
                    history=[m for m in messages[1:-1]],
                )
                fake.calls.append(call)
                if fake.failures:
                    status = fake.failures.pop(0)
                    self._send(status, {"error": {"message": f"fake failure {status}", "type": "fake", "code": str(status)}})
                else:
                    self._send(200, fake.completion(call))

            def _send(self, status: int, payload: dict):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def completion(self, call: Call) -> dict:
        content = json.dumps(self.model.answer(call))
        return {
            "id": "chatcmpl-fake", "object": "chat.completion", "created": 1, "model": "gpt-4o-mini",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content, "refusal": None}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def fail_next(self, status: int, times: int = 1) -> None:
        self.failures.extend([status] * times)

    @property
    def schemas(self) -> list[str]:
        return [call.schema for call in self.calls]

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
