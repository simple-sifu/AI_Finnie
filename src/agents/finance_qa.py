"""Finance Q&A Agent (Story 3.2, FR1): general financial education, grounded in the knowledge base.

It always searches the knowledge base (architecture §7.3) and answers only from
what it finds, citing those articles. If nothing relevant is found, or the
content found doesn't answer the question, it says so instead of guessing.
"""

from __future__ import annotations

from pydantic import Field

from src.agents.base import BaseAgent, LLMAnswer
from src.core.models import AgentName, AgentRequest, AgentResponse, sources_from
from src.rag.retriever import NO_VERIFIED_CONTENT, RetrievedChunk, Retriever

FOLLOW_UP_WORDS = 6  # shorter questions are searched together with the previous one


class GroundedAnswer(LLMAnswer):
    answered_from_content: bool = Field(
        description="True if the verified content below was enough to answer. False if it was not."
    )


GROUNDING_RULES = (
    "Answer ONLY from the verified content above. Do not add facts, numbers or rules that "
    "aren't in it. If the content doesn't answer the question, set answered_from_content to false "
    "and say briefly that you don't have verified information on it. Don't mention the content's "
    "numbering; sources are listed for the user automatically."
)


def context_blocks(results: list[RetrievedChunk]) -> str:
    """The retrieved passages, numbered. Figures that change by year are labeled with their year."""
    blocks = []
    for i, r in enumerate(results, start=1):
        year = f" (figures are for {r.chunk.as_of})" if r.chunk.as_of else ""
        blocks.append(f"[{i}] {r.chunk.title}{year}\n{r.chunk.text}")
    return "\n\n---\n\n".join(blocks)


def build_context(results: list[RetrievedChunk]) -> str:
    return f"Verified content from Finnie's knowledge base:\n\n{context_blocks(results)}\n\n{GROUNDING_RULES}"


def search_query(request: AgentRequest) -> str:
    """Short follow-ups like "what about bonds?" are searched with the previous question for context."""
    if len(request.message.split()) <= FOLLOW_UP_WORDS:
        previous = [turn.content for turn in request.history if turn.role == "user"]
        if previous:
            return f"{previous[-1]} {request.message}"
    return request.message


class FinanceQAAgent(BaseAgent):
    name = AgentName.FINANCE_QA
    instructions = """Your job: answer general questions about personal finance and investing concepts,
such as compound interest, stocks, bonds, funds, diversification and how markets work.
Explain the idea first, then give a short example. Stay general unless the user asks what they should do."""

    def __init__(self, llm, disclaimer_text: str, retriever: Retriever):
        super().__init__(llm, disclaimer_text)
        self.retriever = retriever

    async def _run(self, request: AgentRequest) -> AgentResponse:
        results = await self.retriever.retrieve(search_query(request))
        if not results:
            return AgentResponse(agent=self.name, answer=NO_VERIFIED_CONTENT, response_type="education")

        reply = await self.llm.structured(
            GroundedAnswer,
            f"{self.system_prompt(request.profile)}\n\n{build_context(results)}",
            request.message,
            request.history,
        )
        if not reply.answered_from_content:
            return AgentResponse(agent=self.name, answer=NO_VERIFIED_CONTENT, response_type="education")
        return AgentResponse(
            agent=self.name,
            answer=reply.answer,
            response_type=reply.response_type,
            sources=sources_from(results),
        )
