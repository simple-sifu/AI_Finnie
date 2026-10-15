"""Story 5.1 AC 6 and Story 4.4 AC 4: routing accuracy with the real model.

Calls OpenAI (about 51 short requests), so it only runs when asked:
    RUN_LIVE_TESTS=1 pytest -m live tests/integration/test_routing_live.py
"""

import asyncio
import os
from pathlib import Path

import pytest
import yaml

from src.core.config import load_settings
from src.core.llm import LLMClient
from src.core.models import AgentName, AgentRequest, ChatTurn
from src.workflow.router import Router

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="set RUN_LIVE_TESTS=1 to call OpenAI"),
]
RAW = yaml.safe_load((Path(__file__).parents[1] / "fixtures" / "routing_eval.yaml").read_text())
FOLLOWUPS = RAW.pop("followups")
EVAL = RAW  # the six agents, each with a list of standalone questions


def history_of(item):
    return [ChatTurn(role=t["role"], content=t["content"], agent=AgentName(t["agent"]) if t.get("agent") else None) for t in item["history"]]


def test_test_set_has_at_least_5_questions_per_agent():
    assert set(EVAL) == {name.value for name in AgentName}  # all six agents
    assert all(len(questions) >= 5 for questions in EVAL.values())
    assert sum(len(q) for q in EVAL.values()) >= 30


def test_follow_ups_cover_every_agent_and_start_from_a_different_agent():
    assert {item["expected"] for item in FOLLOWUPS} == {name.value for name in AgentName}
    assert len(FOLLOWUPS) >= 12
    assert sum(item["history"][-1]["agent"] != item["expected"] for item in FOLLOWUPS) >= 8  # the topic changes agent


def test_at_least_90_percent_are_routed_correctly():
    settings = load_settings()
    router = Router(LLMClient.from_settings(settings), settings.router.min_confidence)

    async def classify_all():
        cases = [(route, q, []) for route, questions in EVAL.items() for q in questions]
        cases += [(item["expected"], item["question"], history_of(item)) for item in FOLLOWUPS]
        decisions = await asyncio.gather(*(router.classify(AgentRequest(message=q, history=h)) for _, q, h in cases))
        return [(expected, q, bool(h), d.route) for (expected, q, h), d in zip(cases, decisions)]

    results = asyncio.run(classify_all())
    wrong = [f"{'follow-up' if followup else 'standalone'} {q!r}: expected {e}, got {got}" for e, q, followup, got in results if got != e]
    accuracy = 1 - len(wrong) / len(results)
    standalone = [r for r in results if not r[2]]
    follow = [r for r in results if r[2]]
    print(f"\nrouting accuracy {accuracy:.0%} ({len(results) - len(wrong)}/{len(results)}): "
          f"standalone {sum(e == g for e, _, _, g in standalone)}/{len(standalone)}, "
          f"follow-ups {sum(e == g for e, _, _, g in follow)}/{len(follow)}")
    for line in wrong:
        print("  ", line)
    assert accuracy >= 0.9, wrong
