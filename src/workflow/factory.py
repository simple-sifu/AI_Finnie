"""Build every service and agent from settings (used by the app and live checks)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.agents.base import BaseAgent
from src.agents.finance_qa import FinanceQAAgent
from src.agents.goal_planning import GoalPlanningAgent
from src.agents.market import MarketAgent
from src.agents.news import NewsAgent
from src.agents.portfolio import PortfolioAgent
from src.agents.tax import TaxAgent
from src.core.llm import LLMClient
from src.core.market_data import MarketData
from src.core.models import AgentName
from src.core.news import NewsService
from src.rag.index import IndexLoadError
from src.rag.retriever import Retriever, create_retriever
from src.utils.logging import get_logger, log_event
from src.workflow.graph import FinnieWorkflow
from src.workflow.router import Router

logger = get_logger(__name__)


@dataclass
class FinnieServices:
    settings: object
    llm: LLMClient
    market: MarketData
    news: NewsService
    retriever: Retriever | None  # None if the knowledge base index couldn't load
    agents: dict[AgentName, BaseAgent]
    workflow: FinnieWorkflow


def build_services(settings, cache_dir: Path | None = None) -> FinnieServices:
    llm = LLMClient.from_settings(settings)
    market = MarketData.from_settings(settings, cache_dir=cache_dir)
    news = NewsService.from_settings(settings, cache_dir=cache_dir)
    try:
        retriever = create_retriever(settings)
    except IndexLoadError as exc:
        log_event(logger, "error", kind="index_load", detail=str(exc))
        retriever = None

    disclaimer = settings.disclaimer.text
    agents: dict[AgentName, BaseAgent] = {
        AgentName.PORTFOLIO: PortfolioAgent(llm, disclaimer, market, settings.portfolio.max_rows, settings.portfolio.max_file_mb),
        AgentName.MARKET: MarketAgent(llm, disclaimer, market),
        AgentName.GOAL_PLANNING: GoalPlanningAgent(llm, disclaimer, settings.goals.annual_return),
        AgentName.NEWS: NewsAgent(llm, disclaimer, news),
    }
    if retriever is not None:
        agents[AgentName.FINANCE_QA] = FinanceQAAgent(llm, disclaimer, retriever)
        agents[AgentName.TAX] = TaxAgent(llm, disclaimer, retriever)

    router = Router(llm, settings.router.min_confidence)
    workflow = FinnieWorkflow(router, agents, disclaimer, settings.chat.max_input_chars, settings.chat.timeout_s)
    return FinnieServices(settings, llm, market, news, retriever, agents, workflow)
