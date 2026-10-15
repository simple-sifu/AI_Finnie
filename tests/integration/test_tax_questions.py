"""Story 4.3 AC 5: a tax question set on the real index and embedding model (mocked LLM).

Checks that the right article is found within the Retirement & Tax Accounts
category and cited, and that the 2026 figures reach the model labeled with
their year.
"""

import asyncio

import pytest

from src.agents.tax import TaxAgent, TaxAnswer
from src.core.config import RAGSettings
from src.core.models import AgentRequest
from src.rag.index import load_index, sentence_transformer_embedder
from src.rag.retriever import Retriever

QUESTIONS = [
    ("Should I choose a Roth IRA or a traditional IRA?", "Traditional vs. Roth"),
    ("How much can I contribute to my 401(k) in 2026?", "2026 Retirement Contribution Limits"),
    ("What is a 401(k) and how does it lower my taxes?", "401(k) Plans"),
    ("How are capital gains taxed?", "Capital Gains Taxes"),
    ("What's the difference between short-term and long-term capital gains?", "Capital Gains Taxes"),
    ("What is an HSA?", "Health Savings Accounts (HSAs)"),
    ("What happens if I withdraw from my IRA early?", "Early Withdrawals from Retirement Accounts"),
    ("How does an employer 401(k) match work?", "Employer Matching Contributions"),
    ("How do Roth IRAs work?", "Roth IRAs"),
    ("Can I deduct my traditional IRA contributions?", "Traditional IRAs"),
    ("What is the Roth IRA income limit for singles?", "Roth IRAs"),
    ("What is the catch-up contribution for people over 50?", "2026 Retirement Contribution Limits"),
]


class RecordingLLM:
    def __init__(self):
        self.systems = []

    async def structured(self, schema, system, user, history=None):
        self.systems.append(system)
        return TaxAnswer(answer="Here is the explanation.", response_type="education", answered_from_content=True)


@pytest.fixture(scope="module")
def retriever():
    settings = RAGSettings()
    return Retriever(load_index(), sentence_transformer_embedder(), settings.top_k, settings.min_score)


def test_the_set_has_at_least_10_tax_questions():
    assert len(QUESTIONS) >= 10


@pytest.mark.parametrize("question, expected_title", QUESTIONS)
def test_expected_article_is_cited_and_nothing_outside_the_tax_category_is(retriever, question, expected_title):
    llm = RecordingLLM()
    response = asyncio.run(TaxAgent(llm, "disclaimer", retriever).run(AgentRequest(message=question)))
    assert expected_title in [s.title for s in response.sources]
    assert {s.category for s in response.sources} == {"Retirement & Tax Accounts"}
    assert expected_title in llm.systems[0]


def test_2026_figures_reach_the_model_labeled_with_their_year(retriever):
    llm = RecordingLLM()
    asyncio.run(TaxAgent(llm, "d", retriever).run(AgentRequest(message="How much can I contribute to my 401(k) in 2026?")))
    system = llm.systems[0]
    assert "(figures are for 2026)" in system and "$24,500" in system


@pytest.mark.parametrize("question", ["What's the best pizza in Chicago?", "How do I bake sourdough bread?"])
def test_non_tax_questions_find_nothing(retriever, question):
    llm = RecordingLLM()
    response = asyncio.run(TaxAgent(llm, "d", retriever).run(AgentRequest(message=question)))
    assert response.sources == [] and llm.systems == []
