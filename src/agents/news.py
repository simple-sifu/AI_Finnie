"""News Synthesizer Agent (Story 4.2, FR5).

Turns the user's question into a short news search, gets headlines through
NewsService (so the cache, monthly budget and fallbacks from Story 8.5 apply),
and has the LLM summarize them in plain language and explain why they matter to
a beginner. The agent only has headlines, so it may not add details they don't
contain. Every headline it used is cited with its publisher, date and link.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent, LLMAnswer
from src.core.freshness import DataSource
from src.core.models import AgentName, AgentRequest, AgentResponse, Source
from src.core.news import NewsItem, NewsResult

MAX_HEADLINES = 8  # sent to the LLM
FALLBACK_CITATIONS = 3  # cited if the LLM doesn't say which headlines it used
DEFAULT_QUERY = "stock market"
NO_NEWS = "I couldn't find recent news on that. Try a broader topic, like 'stock market today'."
NEWS_UNAVAILABLE = "I can't get the latest news right now, so I'd rather not guess. Please try again in a little while."

QUERY_PROMPT = """Turn the user's message into a short Google News search query (2 to 6 words) about US finance, markets or the economy.
Use the conversation to resolve references like "that company".
Use these exact queries so repeated questions can reuse earlier results:
- a general request about financial news or the market: "stock market"
- the Federal Reserve or interest rates: "Federal Reserve interest rates"
- inflation or prices: "inflation"
For a specific company or fund, use its name plus "stock" (e.g. "Apple stock"). No dates, no quotation marks."""


class NewsQuery(BaseModel):
    query: str = Field(description="The news search query, 2 to 6 words.")


class NewsSummary(LLMAnswer):
    relevant: bool = Field(description="False if the headlines don't actually address what the user asked.")
    used: list[int] = Field(description="The numbers of the headlines you used in your answer.")


class NewsSource(Protocol):
    async def search(self, query: str) -> NewsResult: ...


def format_headlines(query: str, items: list[NewsItem]) -> str:
    lines = [f"Headlines found for the search '{query}':"]
    for number, item in enumerate(items, start=1):
        when = f", {item.published_at:%b} {item.published_at.day}" if item.published_at else ""
        lines.append(f"{number}. {item.title} ({item.source}{when})")
    return "\n".join(lines)


def to_source(item: NewsItem) -> Source:
    return Source(
        title=item.title,
        url=item.link,
        source_name=item.source,
        category="News",
        published=item.published_at.date() if item.published_at else None,
    )


def cited_items(items: list[NewsItem], used: list[int]) -> list[NewsItem]:
    """The headlines the LLM used, in the order it listed them, without duplicates or bad numbers."""
    chosen = [items[n - 1] for n in dict.fromkeys(used) if 1 <= n <= len(items)]
    return chosen or items[:FALLBACK_CITATIONS]


class NewsAgent(BaseAgent):
    name = AgentName.NEWS
    instructions = """Your job: summarize current financial news for a beginner, using ONLY the numbered headlines below.
- Cover only the 3 or 4 most important stories, grouping related headlines together. Keep the news part under about 100 words, in short sentences or bullets.
- Name the publisher when you report a headline, e.g. "According to Reuters, ...".
- Then add two short sentences on why this kind of news matters to everyday investors, in general terms (for example, what a central bank rate decision usually affects).
- You only have headlines. Don't add facts, numbers, causes or predictions that the headlines don't contain; if they don't say, say you only have the headline.
- Set relevant to false if the headlines don't address what the user asked. In `used`, list the numbers of the headlines you used.
- If the headlines are sample data, say they are examples, not real news.
- Never tell the user what to buy or sell."""

    def __init__(self, llm, disclaimer_text: str, news: NewsSource, max_headlines: int = MAX_HEADLINES):
        super().__init__(llm, disclaimer_text)
        self.news = news
        self.max_headlines = max_headlines

    async def _query(self, request: AgentRequest) -> str:
        found = await self.llm.structured(NewsQuery, QUERY_PROMPT, request.message, request.history)
        return " ".join(found.query.split()) or DEFAULT_QUERY

    async def _run(self, request: AgentRequest) -> AgentResponse:
        query = await self._query(request)
        result = await self.news.search(query)

        if result.source is DataSource.UNAVAILABLE:
            return AgentResponse(agent=self.name, answer=NEWS_UNAVAILABLE, data={"query": query})
        items = result.items[: self.max_headlines]
        if not items:
            return AgentResponse(agent=self.name, answer=NO_NEWS, data={"query": query})

        reply = await self.llm.structured(
            NewsSummary,
            f"{self.system_prompt(request.profile)}\n\n{format_headlines(query, items)}",
            request.message,
            request.history,
        )
        if not reply.relevant:
            return AgentResponse(agent=self.name, answer=NO_NEWS, data={"query": query})

        label = result.label()
        return AgentResponse(
            agent=self.name,
            answer=reply.answer,
            response_type=reply.response_type,
            sources=[to_source(item) for item in cited_items(items, reply.used)],
            labels=[label] if label else [],
            data={"query": query, "headlines": items, "source": result.source.value},
        )
