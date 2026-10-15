"""Story 3.2 AC 4: beginner questions are grounded in the expected article.

Uses the real index and embedding model with a mocked LLM, so it checks that the
right article reaches the model and is cited, without any OpenAI calls.
"""

import asyncio

import pytest

from src.agents.finance_qa import FinanceQAAgent, GroundedAnswer
from src.core.config import RAGSettings
from src.core.models import AgentRequest
from src.rag.index import load_index, sentence_transformer_embedder
from src.rag.retriever import Retriever

QUESTIONS = [
    ("How does compound interest work?", "How Compound Interest Grows Your Money"),
    ("What's the difference between ETFs and mutual funds?", "ETFs vs. Mutual Funds"),
    ("What is a stock?", "What Is a Stock?"),
    ("What is a bond and how does it pay me?", "What Is a Bond?"),
    ("Why is diversification important?", "Diversification"),
    ("What is an index fund?", "Index Funds"),
    ("What is an expense ratio on a fund?", "Expense Ratios"),
    ("How do dividends work?", "Dividends"),
    ("How does inflation affect my savings?", "Inflation and Your Money"),
    ("How fast will my money double?", "The Rule of 72"),
    ("What's the difference between a market order and a limit order?", "Market Orders and Limit Orders"),
    ("What is a bull market?", "Bull and Bear Markets"),
]


class RecordingLLM:
    def __init__(self):
        self.systems = []

    async def structured(self, schema, system, user, history=None):
        self.systems.append(system)
        return GroundedAnswer(answer="ok", response_type="education", answered_from_content=True)


@pytest.fixture(scope="module")
def retriever():
    settings = RAGSettings()
    return Retriever(load_index(), sentence_transformer_embedder(), settings.top_k, settings.min_score)


def test_at_least_10_questions_including_the_required_topics():
    assert len(QUESTIONS) >= 10
    titles = {title for _, title in QUESTIONS}
    assert {"How Compound Interest Grows Your Money", "ETFs vs. Mutual Funds"} <= titles


@pytest.mark.parametrize("question, expected_title", QUESTIONS)
def test_answer_is_grounded_in_the_expected_article(retriever, question, expected_title):
    llm = RecordingLLM()
    response = asyncio.run(FinanceQAAgent(llm, "disclaimer", retriever).run(AgentRequest(message=question)))
    assert expected_title in [s.title for s in response.sources]
    assert expected_title in llm.systems[0]  # the article's content reached the model


def test_create_retriever_uses_configured_settings():
    from src.core.config import load_settings
    from src.rag.retriever import create_retriever

    settings = load_settings(environ={"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"})
    retriever = create_retriever(settings)
    assert retriever.top_k == settings.rag.top_k and retriever.min_score == settings.rag.min_score
    assert retriever.search("What is compound interest?")
