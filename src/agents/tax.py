"""Tax Education Agent (Story 4.3, FR6).

Explains US tax concepts and account types (401(k), IRA, Roth, HSA, capital
gains) from the knowledge base only, searching just the Retirement & Tax
Accounts category and citing what it used. It may give advice (D-7), with the
disclaimer.

Tax figures change every year, so they must never come from the model's own
memory (Story 4.3 AC 3). Three safeguards:
1. passages carry the year their figures are for, and the prompt says to state it;
2. a check compares every dollar amount and percentage in the answer with the
   retrieved content and the user's question; sentences with a figure that isn't
   there are removed, and if too little is left, a safe message points to the IRS;
3. when an answer gives dollar figures without naming their year, the year is added.
"""

from __future__ import annotations

import logging
import re

from pydantic import Field

from src.agents.base import BaseAgent
from src.agents.finance_qa import GROUNDING_RULES, GroundedAnswer, context_blocks, search_query
from src.core.categories import RETIREMENT_AND_TAX_ACCOUNTS
from src.core.models import AgentName, AgentRequest, AgentResponse, sources_from
from src.rag.retriever import NO_VERIFIED_CONTENT, RetrievedChunk, Retriever
from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)

TAX_CATEGORIES = [RETIREMENT_AND_TAX_ACCOUNTS]
US_ONLY = (
    "I only cover US taxes and retirement accounts, like the 401(k), IRA, Roth IRA and HSA, "
    "so I can't help with another country's rules."
)
UNVERIFIED_FIGURES = (
    "Tax limits and thresholds change every year, and I couldn't confirm the exact figures you need from "
    "my verified content, so I'd rather not guess. The IRS publishes the current numbers at irs.gov."
)

MIN_WORDS_AFTER_STRIPPING = 15  # a shorter remainder isn't a useful answer
_NON_US = re.compile(
    r"\b(uk|u\.k\.|united kingdom|british|britain|england|isa|sipp|hmrc|canada|canadian|rrsp|tfsa|australia|australian|"
    r"superannuation|india|indian|germany|german|france|french|europe|european|japan|japanese|china|chinese|mexico)\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b(20\d{2})\b")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


class TaxAnswer(GroundedAnswer):
    """Grounded tax answer; flags non-US questions the agent must decline."""

    non_us: bool = Field(default=False, description="True if the question is about another country's tax rules.")


def unsupported_figures(answer: str, support: str) -> list[str]:
    """Dollar amounts and percentages in `answer` that appear nowhere in `support`.

    `support` is the retrieved content plus the user's own message, so a number the user
    gave can be repeated, but a limit the model remembered from training cannot.
    """
    known = {float(n.replace(",", "")) for n in _NUMBER.findall(support)}
    problems = [f"${m}" for m in _MONEY.findall(answer) if float(m.replace(",", "")) not in known]
    problems += [f"{m}%" for m in _PERCENT.findall(answer) if float(m) not in known]
    return list(dict.fromkeys(problems))


def strip_unsupported(answer: str, support: str) -> tuple[str, int]:
    """Remove the sentences that contain an unsupported figure. Returns the rest and how many were removed.

    Models like to add made-up examples ("if you made $1,000..."). Dropping just those
    sentences keeps the useful, grounded part of the answer.
    """
    removed, kept_lines = 0, []
    for line in answer.split("\n"):
        kept = []
        for sentence in _SENTENCE_END.split(line):
            if sentence and unsupported_figures(sentence, support):
                removed += 1
            elif sentence:
                kept.append(sentence)
        kept_lines.append(" ".join(kept))
    text = "\n".join(kept_lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip(), removed


def year_hint(message: str, results: list[RetrievedChunk]) -> str:
    """If the user asks about a year the content doesn't cover, tell the model how to answer."""
    covered = {r.chunk.as_of for r in results if r.chunk.as_of}
    asked = {int(y) for y in _YEAR.findall(message)} - covered
    if not covered or not asked:
        return ""
    have = " and ".join(str(y) for y in sorted(covered))
    want = " and ".join(str(y) for y in sorted(asked))
    return (
        f"\n\nThe user mentioned {want}, but the content only has figures for {have}. Give the {have} figures, "
        f"clearly labeled as {have}, say you don't have {want}'s figures (irs.gov has them), and set "
        "answered_from_content to true."
    )


def with_figure_year(answer: str, results: list[RetrievedChunk]) -> str:
    """If the answer quotes dollar figures but never names the year they are for, say so."""
    years = sorted({r.chunk.as_of for r in results if r.chunk.as_of})
    if not years or not _MONEY.search(answer) or any(str(year) in answer for year in years):
        return answer
    label = " and ".join(str(year) for year in years)
    return f"{answer.rstrip()}\n\n_Dollar figures here are for {label}. They change every year, so check irs.gov for the latest._"


class TaxAgent(BaseAgent):
    """US tax and retirement account education grounded in the knowledge base."""

    name = AgentName.TAX
    instructions = """Your job: explain US tax concepts and account types for beginners, such as the 401(k), traditional and Roth IRAs, HSAs, employer matches, early withdrawals and capital gains.
Explain the idea first, then a short example. Finnie covers the United States only: if the question is about another country's taxes, set non_us to true.
You may recommend what suits the user (for example Roth or traditional) when they ask, but explain the trade-offs and base it on the content.
Tax figures change every year. Use a dollar amount, income threshold or rate ONLY if it appears in the verified content, and always say which year it is for ("for 2026"). If the user asks about a different year than the content covers, or the content doesn't have the figure, say you only have the figures shown and that the IRS (irs.gov) has the rest. Never fill in a figure from memory. If you give an example, use only numbers from the content or from the user's message."""

    def __init__(self, llm, disclaimer_text: str, retriever: Retriever):
        super().__init__(llm, disclaimer_text)
        self.retriever = retriever

    async def _run(self, request: AgentRequest) -> AgentResponse:
        results = await self.retriever.retrieve(search_query(request), categories=TAX_CATEGORIES)
        if not results:
            # Nothing relevant: if the question names another country, say Finnie covers the US only.
            return AgentResponse(agent=self.name, answer=US_ONLY if _NON_US.search(request.message) else NO_VERIFIED_CONTENT)

        system = (
            f"{self.system_prompt(request.profile)}\n\nVerified content:\n\n{context_blocks(results)}\n\n{GROUNDING_RULES}"
            f"{year_hint(request.message, results)}"
        )
        reply = await self.llm.structured(TaxAnswer, system, request.message, request.history)
        if reply.non_us:
            return AgentResponse(agent=self.name, answer=US_ONLY)
        if not reply.answered_from_content:
            return AgentResponse(agent=self.name, answer=NO_VERIFIED_CONTENT)

        support = " ".join(r.chunk.text for r in results) + " " + request.message
        sources = sources_from(results)
        text, removed = strip_unsupported(reply.answer, support)
        if removed:
            log_event(logger, "unsupported_figures", level=logging.WARNING, sentences_removed=removed)
            if len(text.split()) < MIN_WORDS_AFTER_STRIPPING:
                return AgentResponse(agent=self.name, answer=UNVERIFIED_FIGURES, sources=sources)

        return AgentResponse(
            agent=self.name,
            answer=with_figure_year(text, results),
            response_type=reply.response_type,
            sources=sources,
        )
