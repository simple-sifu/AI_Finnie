"""Story 3.2: Finance Q&A Agent (fake retriever and fake LLM)."""

import asyncio

from src.agents.base import LLM_UNAVAILABLE
from src.agents.finance_qa import FinanceQAAgent, GroundedAnswer, search_query
from src.core.llm import LLMUnavailableError
from src.core.models import AgentName, AgentRequest, ChatTurn
from src.rag.chunking import Chunk
from src.rag.retriever import NO_VERIFIED_CONTENT, RetrievedChunk

DISCLAIMER = "Not personalized advice."


def hit(slug, title, text, score=0.8):
    return RetrievedChunk(Chunk(f"{slug}#0", f"{title}\n\n{text}", "article", slug, title, "Investing Basics",
                                "Investor.gov (U.S. SEC)", f"https://www.investor.gov/{slug}"), score)


COMPOUND = hit("compound-interest", "How Compound Interest Grows Your Money", "Compounding is interest on interest.")


class FakeRetriever:
    def __init__(self, results=None, error=None):
        self.results, self.error, self.queries = results or [], error, []

    async def retrieve(self, query, k=None, categories=None):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.results


class FakeLLM:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    async def structured(self, schema, system, user, history=None):
        self.calls.append({"schema": schema, "system": system, "user": user})
        if self.error:
            raise self.error
        return self.reply


def answer(text="Compounding means earning interest on interest.", kind="education", grounded=True):
    return GroundedAnswer(answer=text, response_type=kind, answered_from_content=grounded)


def run(agent, message="What is compound interest?", history=()):
    return asyncio.run(agent.run(AgentRequest(message=message, history=list(history))))


def test_grounded_answer_lists_its_sources():
    llm = FakeLLM(answer())
    response = run(FinanceQAAgent(llm, DISCLAIMER, FakeRetriever([COMPOUND])))
    assert response.agent is AgentName.FINANCE_QA and response.answer.startswith("Compounding")
    assert [s.title for s in response.sources] == ["How Compound Interest Grows Your Money"]
    assert response.disclaimer is None and not response.error


def test_retrieved_content_and_grounding_rules_go_to_the_llm():
    llm = FakeLLM(answer())
    run(FinanceQAAgent(llm, DISCLAIMER, FakeRetriever([COMPOUND])))
    system = llm.calls[0]["system"]
    assert "Compounding is interest on interest." in system
    assert "Answer ONLY from the verified content" in system and llm.calls[0]["schema"] is GroundedAnswer


def test_nothing_relevant_says_so_without_calling_the_llm():
    llm = FakeLLM(answer())
    response = run(FinanceQAAgent(llm, DISCLAIMER, FakeRetriever([])), message="Best pizza in Chicago?")
    assert response.answer == NO_VERIFIED_CONTENT and response.sources == [] and llm.calls == []


def test_content_that_doesnt_answer_the_question_is_not_guessed_from():
    llm = FakeLLM(answer("I'm not sure.", grounded=False))
    response = run(FinanceQAAgent(llm, DISCLAIMER, FakeRetriever([COMPOUND])), message="What's the P/E ratio?")
    assert response.answer == NO_VERIFIED_CONTENT and response.sources == []


def test_advice_answers_get_the_disclaimer():
    llm = FakeLLM(answer("You should start investing now.", kind="advice"))
    response = run(FinanceQAAgent(llm, DISCLAIMER, FakeRetriever([COMPOUND])))
    assert response.disclaimer == DISCLAIMER and response.sources


def test_short_follow_up_is_searched_with_the_previous_question():
    history = [ChatTurn(role="user", content="What is a stock?"), ChatTurn(role="assistant", content="A share...")]
    assert search_query(AgentRequest(message="what about bonds?", history=history)) == "What is a stock? what about bonds?"
    long_question = "How do bonds pay interest and what happens when they mature?"
    assert search_query(AgentRequest(message=long_question, history=history)) == long_question
    assert search_query(AgentRequest(message="what about bonds?")) == "what about bonds?"


def test_search_failure_becomes_a_friendly_message():
    response = run(FinanceQAAgent(FakeLLM(answer()), DISCLAIMER, FakeRetriever(error=RuntimeError("index broke"))))
    assert response.error and "something went wrong" in response.answer


def test_llm_unavailable_becomes_a_friendly_message():
    llm = FakeLLM(error=LLMUnavailableError("APIConnectionError"))
    response = run(FinanceQAAgent(llm, DISCLAIMER, FakeRetriever([COMPOUND])))
    assert response.error and response.answer == LLM_UNAVAILABLE
