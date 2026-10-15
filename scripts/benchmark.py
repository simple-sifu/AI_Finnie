#!/usr/bin/env python3
"""Measure Finnie against NFR13 targets (Story 9.4).

Runs offline with the same fake OpenAI, Alpha Vantage and SerpApi used in integration
tests, so it costs nothing and is repeatable in CI. Writes docs/benchmarks.md.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --output docs/benchmarks.md
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import respx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.async_runner import AsyncRunner  # noqa: E402
from src.core.calculators import Position, calculate  # noqa: E402
from src.core.config import load_settings  # noqa: E402
from src.core.funds import lookup_expense_ratio  # noqa: E402
from src.core.models import AgentRequest  # noqa: E402
from src.rag.index import load_index, sentence_transformer_embedder  # noqa: E402
from src.rag.retriever import Retriever  # noqa: E402
from src.core.market_data import MarketData, Quote  # noqa: E402
from src.workflow import factory as factory_module  # noqa: E402
from tests.integration.support import PRICES, FakeAlphaVantage, FakeOpenAI, FakeSerpApi  # noqa: E402

KEYS = {
    "OPENAI_API_KEY": "sk-bench-openai",
    "ALPHA_VANTAGE_API_KEY": "av-bench-key",
    "SERPAPI_API_KEY": "serp-bench-key",
}

CHAT_QUESTIONS = [
    "What is compound interest?",
    "What is an ETF?",
    "How is VTI doing?",
    "How is SPY doing?",
    "I want $20,000 in 4 years. I have $3,000 saved.",
    "moderate",
    "Should I choose a Roth IRA or a traditional IRA?",
    "What's in the financial news today?",
    "How is QQQ doing?",
    "Explain diversification in one sentence.",
    "What is a 401(k)?",
]

RETRIEVAL_QUERIES = [
    "What is compound interest?",
    "ETF vs mutual fund",
    "Roth IRA rules",
    "How does diversification work?",
    "What is an expense ratio?",
]

TICKERS_FOR_PORTFOLIO = list(PRICES.keys())


@dataclass(frozen=True)
class Target:
    name: str
    limit: str
    measured: str
    passed: bool
    note: str = ""


def _ms(seconds: float) -> float:
    return seconds * 1000


def _fmt_seconds(seconds: float) -> str:
    if seconds < 1:
        return f"{_ms(seconds):.0f} ms"
    return f"{seconds:.2f} s"


def _bench_environ(openai_base: str | None = None) -> dict[str, str]:
    env = {
        **KEYS,
        "FINNIE_MARKET__PER_MINUTE_LIMIT": "100",
        "FINNIE_MARKET__MIN_INTERVAL_SECONDS": "0",
    }
    if openai_base:
        env["OPENAI_BASE_URL"] = openai_base
    return env


def _load_retriever(settings) -> Retriever:
    index = load_index()
    embed = sentence_transformer_embedder()
    retriever = Retriever(index, embed, settings.rag.top_k, settings.rag.min_score)
    retriever.warm_up()
    return retriever


def measure_cold_startup() -> tuple[float, Retriever, object]:
    """Cold load: FAISS index, embedding model warm-up, and service wiring (no HTTP mocks)."""
    environ = _bench_environ()
    for name, value in environ.items():
        os.environ[name] = value
    t0 = time.perf_counter()
    settings = load_settings(environ=environ)
    retriever = _load_retriever(settings)
    factory_module.create_retriever = lambda _settings: retriever  # type: ignore[method-assign]
    with tempfile.TemporaryDirectory() as tmp:
        factory_module.build_services(settings, cache_dir=Path(tmp))
    elapsed = time.perf_counter() - t0
    return elapsed, retriever, settings


def _services_with_fakes(
    cache_dir: Path, router: respx.MockRouter, openai: FakeOpenAI, retriever: Retriever, settings
):
    alpha, serp = FakeAlphaVantage(), FakeSerpApi()
    alpha.install(router)
    serp.install(router)
    environ = _bench_environ(openai.base_url)
    for name, value in environ.items():
        os.environ[name] = value
    settings = load_settings(environ=environ)
    factory_module.create_retriever = lambda _settings: retriever  # type: ignore[method-assign]
    runner = AsyncRunner()
    services = factory_module.build_services(settings, cache_dir=cache_dir)
    services.llm.retry_base_seconds = 0
    return settings, services, runner, alpha


def measure_retrieval(retriever: Retriever) -> float:
    """Worst-case retrieval time after warm-up (NFR13: ≤300 ms per query)."""
    for query in RETRIEVAL_QUERIES:
        retriever.search(query)
    timings = []
    for query in RETRIEVAL_QUERIES:
        t0 = time.perf_counter()
        retriever.search(query)
        timings.append(time.perf_counter() - t0)
    return max(timings)


async def measure_market(settings, cache_dir: Path, alpha: FakeAlphaVantage) -> tuple[float, float]:
    """Cached hit vs live miss (fake HTTP) for one quote."""
    market = MarketData.from_settings(settings, cache_dir=cache_dir)
    await market.get_quote("VTI")
    t0 = time.perf_counter()
    await market.get_quote("VTI")
    cached = time.perf_counter() - t0

    live_dir = cache_dir / "live"
    live_dir.mkdir(exist_ok=True)
    alpha.calls.clear()
    market_live = MarketData.from_settings(settings, cache_dir=live_dir)
    t0 = time.perf_counter()
    await market_live.get_quote("SPY")
    live = time.perf_counter() - t0
    return cached, live


async def measure_portfolio_metrics(market) -> float:
    """Price 50 holdings from cache, then calculate metrics (no LLM)."""
    tickers = (TICKERS_FOR_PORTFOLIO * 5)[:50]
    for ticker in dict.fromkeys(tickers):
        await market.get_quote(ticker)

    async def price_all() -> None:
        positions: list[Position] = []
        for ticker in tickers:
            result = await market.get_quote(ticker)
            price = result.value.price if isinstance(result.value, Quote) else None
            lookup = lookup_expense_ratio(ticker, None)
            positions.append(Position(ticker, 10.0, price, lookup.asset_type, lookup.expense_ratio))
        calculate(positions)

    t0 = time.perf_counter()
    await price_all()
    return time.perf_counter() - t0


def measure_chat(services, runner: AsyncRunner) -> tuple[float, float]:
    latencies = []
    for question in CHAT_QUESTIONS:
        request = AgentRequest(message=question)
        t0 = time.perf_counter()
        runner.run(services.workflow.run(request))
        latencies.append(time.perf_counter() - t0)
    latencies.sort()
    median = statistics.median(latencies)
    p90 = latencies[max(0, int(len(latencies) * 0.9) - 1)]
    return median, p90


def check_holdings_limits(settings) -> Target:
    ok = settings.portfolio.max_rows == 200 and settings.portfolio.max_file_mb == 1.0
    return Target(
        "Holdings upload limit",
        "200 rows or 1 MB",
        f"{settings.portfolio.max_rows} rows, {settings.portfolio.max_file_mb} MB",
        ok,
    )


def run_benchmarks() -> list[Target]:
    results: list[Target] = []

    startup, retriever, _base_settings = measure_cold_startup()
    results.append(Target("App startup (index + embedder + services)", "≤ 10 s", _fmt_seconds(startup), startup <= 10.0))

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp)
        openai = FakeOpenAI()
        runner: AsyncRunner | None = None
        try:
            with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
                settings, services, runner, alpha = _services_with_fakes(
                    cache_dir, router, openai, retriever, _base_settings
                )

                retrieval = measure_retrieval(retriever)
                results.append(Target(
                    "Knowledge-base retrieval (max of 5 queries, warmed)",
                    "≤ 300 ms",
                    _fmt_seconds(retrieval),
                    retrieval <= 0.3,
                ))

                cached, live = asyncio.run(measure_market(settings, cache_dir, alpha))
                results.append(Target("Market quote (cache hit)", "≤ 1 s", _fmt_seconds(cached), cached <= 1.0))
                results.append(Target("Market quote (live fake API)", "≤ 3 s", _fmt_seconds(live), live <= 3.0))

                portfolio = asyncio.run(measure_portfolio_metrics(services.market))
                results.append(Target(
                    "Portfolio metrics (50 holdings, cached prices, no LLM)",
                    "≤ 2 s",
                    _fmt_seconds(portfolio),
                    portfolio <= 2.0,
                ))

                chat_median, chat_p90 = measure_chat(services, runner)
                results.append(Target("Chat latency (median, 11 questions)", "≤ 6 s", _fmt_seconds(chat_median), chat_median <= 6.0))
                results.append(Target("Chat latency (p90, 11 questions)", "≤ 12 s", _fmt_seconds(chat_p90), chat_p90 <= 12.0))

                results.append(check_holdings_limits(settings))
        finally:
            openai.close()
            if runner is not None:
                runner.close()

    return results


def render_markdown(results: list[Target], output: Path) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    passed = all(r.passed for r in results)
    lines = [
        "---",
        "title: Finnie — Performance Benchmarks",
        "story: 9.4",
        f"generated: {now}",
        "---",
        "",
        "# Performance benchmarks (NFR13)",
        "",
        "Generated by [`scripts/benchmark.py`](../scripts/benchmark.py). Targets are from [`docs/prd.md`](prd.md) NFR13 and [`docs/architecture.md`](architecture.md) §15.",
        "",
        "Measurements use the **offline fake stack** (same as integration tests): instant fake OpenAI, Alpha Vantage and SerpApi. Chat times therefore reflect router + agent + local RAG and cache work, not network latency to real APIs.",
        "",
        f"**Overall:** {'**Pass** — all targets met.' if passed else '**Review** — one or more targets missed (see notes).'}",
        "",
        "| Target | Limit | Measured | Result | Notes |",
        "|---|---|---|---|---|",
    ]
    for row in results:
        status = "Pass" if row.passed else "Miss"
        note = row.note or ("—" if row.passed else "See Story 9.4 AC 3")
        lines.append(f"| {row.name} | {row.limit} | {row.measured} | {status} | {note} |")
    lines.extend([
        "",
        "## How to re-run",
        "",
        "```bash",
        "python scripts/benchmark.py",
        "```",
        "",
        "## Misses and agreed exceptions",
        "",
        "None recorded. If a target fails on a slow machine, re-run after closing other apps; chat targets use fake LLM and should stay well under the limit.",
        "",
    ])
    output.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Finnie against NFR13 performance targets.")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "benchmarks.md")
    args = parser.parse_args()

    results = run_benchmarks()
    render_markdown(results, args.output)
    print(f"Wrote {args.output}")
    for row in results:
        mark = "OK" if row.passed else "MISS"
        print(f"  [{mark}] {row.name}: {row.measured} (limit {row.limit})")
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
