"""Story 4.3: Tax Education Agent (fake retriever and fake LLM)."""

import asyncio

import pytest

from src.agents.finance_qa import context_blocks
from src.agents.tax import (
    TAX_CATEGORIES,
    UNVERIFIED_FIGURES,
    US_ONLY,
    TaxAgent,
    TaxAnswer,
    strip_unsupported,
    unsupported_figures,
    with_figure_year,
    year_hint,
)
from src.core.models import AgentName, AgentRequest, format_sources
from src.rag.chunking import Chunk
from src.rag.retriever import NO_VERIFIED_CONTENT, RetrievedChunk

DISCLAIMER = "Not personalized tax advice."


def hit(slug, title, text, as_of=None, score=0.8):
    chunk = Chunk(f"{slug}#0", f"{title}\n\n{text}", "article", slug, title, "Retirement & Tax Accounts",
                  "IRS.gov (Internal Revenue Service)", f"https://www.irs.gov/{slug}", as_of)
    return RetrievedChunk(chunk, score)


LIMITS = hit("limits", "2026 Retirement Contribution Limits",
             "The employee contribution limit is $24,500. The IRA limit is $7,500, plus $1,100 catch-up at 50 or older.", as_of=2026)
EARLY = hit("early", "Early Withdrawals", "A 10% additional tax usually applies before age 59½. Withdrawing $10,000 could cost $1,000.")


class FakeRetriever:
    def __init__(self, results=None):
        self.results, self.calls = results or [], []

    async def retrieve(self, query, k=None, categories=None):
        self.calls.append({"query": query, "categories": categories})
        return self.results


class FakeLLM:
    """Returns scripted answers in order, and records every system prompt."""

    def __init__(self, *answers):
        self.answers, self.systems = list(answers), []

    async def structured(self, schema, system, user, history=None):
        self.systems.append(system)
        return self.answers.pop(0)


def answer(text, kind="education", grounded=True, non_us=False):
    return TaxAnswer(answer=text, response_type=kind, answered_from_content=grounded, non_us=non_us)


def ask(*answers, results=None, message="What is the 401(k) limit?"):
    retriever, llm = FakeRetriever(results if results is not None else [LIMITS]), FakeLLM(*answers)
    response = asyncio.run(TaxAgent(llm, DISCLAIMER, retriever).run(AgentRequest(message=message)))
    return response, retriever, llm


# --- AC 2: only the Retirement & Tax Accounts category, with citations ---


def test_it_searches_only_the_tax_category_and_cites_what_it_used():
    response, retriever, _ = ask(answer("For 2026 the limit is $24,500."))
    assert retriever.calls[0]["categories"] == TAX_CATEGORIES == ["Retirement & Tax Accounts"]
    assert response.agent is AgentName.TAX
    assert [s.title for s in response.sources] == ["2026 Retirement Contribution Limits"]
    assert response.sources[0].as_of == 2026 and "(as of 2026)" in format_sources(response.sources)


def test_nothing_in_the_category_says_so_without_calling_the_llm():
    response, _, llm = ask(results=[])
    assert response.answer == NO_VERIFIED_CONTENT and llm.systems == []


def test_content_that_does_not_answer_is_not_guessed_from():
    assert ask(answer("not sure", grounded=False))[0].answer == NO_VERIFIED_CONTENT


# --- AC 1: US only ---


def test_other_countries_get_a_clear_us_only_message():
    response, _, _ = ask(answer("In the UK an ISA works...", non_us=True), message="How does a UK ISA work?")
    assert response.answer == US_ONLY and response.sources == []


def test_the_prompt_says_us_only_and_names_the_covered_accounts():
    _, _, llm = ask(answer("ok"))
    for phrase in ("United States only", "401(k)", "HSAs", "capital gains", "another country"):
        assert phrase in llm.systems[0]


# --- AC 3: figures that change by year come from the knowledge base, with their year ---


def test_passages_are_labeled_with_the_year_their_figures_are_for():
    context = context_blocks([LIMITS, EARLY])
    assert "[1] 2026 Retirement Contribution Limits (figures are for 2026)" in context
    assert "[2] Early Withdrawals\n" in context  # no year on content without year-specific figures


def test_the_prompt_forbids_figures_from_memory_and_asks_for_the_year():
    _, _, llm = ask(answer("ok"))
    system = llm.systems[0]
    assert "ONLY if it appears in the verified content" in system and "Never fill in a figure from memory" in system
    assert 'say which year it is for ("for 2026")' in system and "irs.gov" in system


def test_figures_that_are_in_the_content_are_not_flagged():
    support = "limit $24,500. IRA $7,500. catch-up $1,100. total $32,500."
    assert unsupported_figures("The 2026 limit is $24,500, or $32,500 if 50 or older.", support) == []


def test_a_remembered_figure_is_caught():
    support = LIMITS.chunk.text
    assert unsupported_figures("The limit is $23,000.", support) == ["$23,000"]
    assert unsupported_figures("The 2027 limit is $25,000 and the IRA limit $8,000.", support) == ["$25,000", "$8,000"]
    assert unsupported_figures("You'd pay 22% in the bracket.", support) == ["22%"]


def test_figures_from_the_content_or_the_users_own_message_are_allowed():
    support = EARLY.chunk.text + " If I withdraw $4,000 early what happens?"
    assert unsupported_figures("A 10% additional tax applies, so on $10,000 that's $1,000, and on your $4,000 it's less.", support) == []
    assert unsupported_figures("Withdrawing $10,000.00 costs $1000", support) == []  # formatting differences don't matter


def test_answers_without_figures_are_never_flagged():
    assert unsupported_figures("A Roth IRA is funded with after-tax money.", "") == []


def test_sentences_with_remembered_figures_are_removed_and_the_grounded_rest_is_kept():
    mixed = answer("Withdrawing early usually costs a 10% additional tax. For example, on $5,000 you would owe $500 in penalty. "
                   "There are exceptions, such as disability or a first home purchase.")
    response, _, llm = ask(mixed, results=[EARLY])
    assert "10% additional tax" in response.answer and "exceptions" in response.answer
    assert "$500" not in response.answer and "$5,000" not in response.answer
    assert len(llm.systems) == 1  # a single LLM call: nothing is rewritten


def test_made_up_examples_do_not_throw_away_a_good_answer():
    capital_gains = hit("cg", "Capital Gains Taxes", "Long-term gains are taxed at 0%, 15% or 20% depending on income.")
    text = ("Long-term capital gains, from investments held more than a year, are taxed at 0%, 15% or 20% depending on your income. "
            "For example, a $1,000 gain taxed at 15% costs $150.")
    response, _, _ = ask(answer(text), results=[capital_gains])
    assert response.answer.startswith("Long-term capital gains") and "$150" not in response.answer and "$1,000" not in response.answer


def test_if_too_little_is_left_a_safe_message_points_to_the_irs():
    response, _, _ = ask(answer("The limit is $23,000."))
    assert response.answer == UNVERIFIED_FIGURES and "irs.gov" in response.answer
    assert [s.title for s in response.sources] == ["2026 Retirement Contribution Limits"]


def test_strip_unsupported_keeps_paragraphs_and_bullets():
    support = "A 10% additional tax applies."
    text = "A 10% additional tax applies.\n\n- It could cost $999 extra.\n- Exceptions exist."
    stripped, removed = strip_unsupported(text, support)
    assert removed == 1 and stripped == "A 10% additional tax applies.\n\n\n- Exceptions exist.".replace("\n\n\n", "\n\n")
    assert strip_unsupported("Nothing to remove here.", support) == ("Nothing to remove here.", 0)


# --- years the knowledge base doesn't cover ---


def test_a_year_the_content_does_not_cover_is_explained_to_the_model():
    hint = year_hint("What is the 401(k) limit for 2027?", [LIMITS])
    assert "mentioned 2027" in hint and "only has figures for 2026" in hint and "set answered_from_content to true" in hint
    assert year_hint("What is the 401(k) limit for 2026?", [LIMITS]) == ""  # covered
    assert year_hint("What is the limit for 2027?", [EARLY]) == ""  # nothing year-specific retrieved
    assert year_hint("What is the limit?", [LIMITS]) == ""


def test_the_other_year_hint_reaches_the_model_in_a_real_flow():
    _, _, llm = ask(answer("For 2026 the limit is $24,500. I don't have 2027's figures."), message="What's the 2027 401(k) limit?")
    assert "The user mentioned 2027" in llm.systems[0]


@pytest.mark.parametrize("question", ["How does a UK ISA work?", "Explain the Canadian RRSP", "What is superannuation in Australia?", "Tell me about HMRC rules"])
def test_other_countries_are_recognized_when_nothing_was_found(question):
    assert ask(results=[], message=question)[0].answer == US_ONLY


def test_a_plain_unknown_question_still_gets_the_generic_decline():
    assert ask(results=[], message="How do I bake bread?")[0].answer == NO_VERIFIED_CONTENT


def test_a_year_is_added_when_dollar_figures_do_not_say_which_year():
    text = with_figure_year("The limit is $24,500.", [LIMITS])
    assert text.endswith("_Dollar figures here are for 2026. They change every year, so check irs.gov for the latest._")
    assert with_figure_year("For 2026 the limit is $24,500.", [LIMITS]) == "For 2026 the limit is $24,500."
    assert with_figure_year("A Roth IRA is after-tax.", [LIMITS]) == "A Roth IRA is after-tax."  # no dollar figures
    assert with_figure_year("It costs $1,000.", [EARLY]) == "It costs $1,000."  # no year-specific content used


def test_the_year_is_added_in_a_full_answer():
    response, _, _ = ask(answer("The employee limit is $24,500."))
    assert "Dollar figures here are for 2026" in response.answer


# --- AC 4: advice gets the disclaimer ---


@pytest.mark.parametrize("kind, shown", [("education", False), ("advice", True), ("uncertain", True)])
def test_advice_answers_carry_the_disclaimer(kind, shown):
    response, _, _ = ask(answer("A Roth could suit you if you expect higher taxes later.", kind=kind))
    assert (response.disclaimer == DISCLAIMER) is shown


# --- follow-ups and wiring ---


def test_short_follow_ups_are_searched_with_the_previous_question():
    from src.core.models import ChatTurn

    retriever, llm = FakeRetriever([LIMITS]), FakeLLM(answer("ok"))
    history = [ChatTurn(role="user", content="Tell me about the Roth IRA"), ChatTurn(role="assistant", content="...")]
    asyncio.run(TaxAgent(llm, DISCLAIMER, retriever).run(AgentRequest(message="what about the limit?", history=history)))
    assert retriever.calls[0]["query"] == "Tell me about the Roth IRA what about the limit?"


def test_it_is_registered_in_the_workflow(tmp_path, monkeypatch):
    from src.core.config import load_settings
    from src.workflow import factory

    retriever = FakeRetriever()
    monkeypatch.setattr(factory, "create_retriever", lambda settings: retriever)
    keys = {"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}
    services = factory.build_services(load_settings(config_path=tmp_path / "none.yaml", environ=keys), cache_dir=tmp_path)
    assert isinstance(services.agents[AgentName.TAX], TaxAgent) and services.agents[AgentName.TAX].retriever is retriever
