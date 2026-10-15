"""Story 5.1 AC 6: routing accuracy with the real model.

Calls OpenAI (36 short requests), so it only runs when asked:
    RUN_LIVE_TESTS=1 pytest -m live tests/integration/test_routing_live.py
"""

import asyncio
import os
from pathlib import Path

import pytest
import yaml

from src.core.config import load_settings
from src.core.llm import LLMClient
from src.core.models import AgentRequest
from src.workflow.router import Router

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="set RUN_LIVE_TESTS=1 to call OpenAI"),
]
EVAL = yaml.safe_load((Path(__file__).parents[1] / "fixtures" / "routing_eval.yaml").read_text())


def test_test_set_has_at_least_5_questions_per_agent():
    assert len(EVAL) == 6 and all(len(questions) >= 5 for questions in EVAL.values())
    assert sum(len(q) for q in EVAL.values()) >= 30


def test_at_least_90_percent_are_routed_correctly():
    settings = load_settings()
    router = Router(LLMClient.from_settings(settings), settings.router.min_confidence)

    async def classify_all():
        items = [(route, q) for route, questions in EVAL.items() for q in questions]
        decisions = await asyncio.gather(*(router.classify(AgentRequest(message=q)) for _, q in items))
        return [(expected, q, d.route) for (expected, q), d in zip(items, decisions)]

    results = asyncio.run(classify_all())
    wrong = [f"{q!r}: expected {e}, got {got}" for e, q, got in results if got != e]
    accuracy = 1 - len(wrong) / len(results)
    print(f"\nrouting accuracy {accuracy:.0%} ({len(results) - len(wrong)}/{len(results)})")
    for line in wrong:
        print("  ", line)
    assert accuracy >= 0.9, wrong
