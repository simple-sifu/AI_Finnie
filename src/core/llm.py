"""The one shared OpenAI client for all agents (Story 3.1, D-6, NFR5).

- Model from OPENAI_MODEL (default gpt-4o-mini).
- At most `llm.max_concurrent` calls at once (a semaphore), so a burst of
  requests can't trip OpenAI's rate limits.
- Rate-limit, timeout and server errors are retried with exponential backoff,
  up to `llm.max_retries` times; anything else fails at once.
- After retries are used up, LLMUnavailableError is raised, which agents turn
  into a friendly "temporarily unavailable" message.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TypeVar

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.models import ChatTurn
from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)

RETRYABLE = (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)


class LLMUnavailableError(Exception):
    """OpenAI couldn't be reached or kept failing after retries."""


class LLMClient:
    def __init__(
        self,
        chat_model: Any,
        max_concurrent: int = 4,
        max_retries: int = 3,
        retry_base_seconds: float = 1.0,
    ):
        self.chat_model = chat_model
        self.max_retries = max_retries
        self.retry_base_seconds = retry_base_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent)

    @classmethod
    def from_settings(cls, settings) -> LLMClient:
        llm = settings.llm
        chat_model = ChatOpenAI(
            model=llm.model,
            temperature=llm.temperature,
            timeout=llm.timeout_s,
            max_retries=0,  # retries are handled here, with logging
            api_key=settings.secrets.openai_api_key.get_secret_value(),
        )
        return cls(chat_model, llm.max_concurrent, llm.max_retries)

    @staticmethod
    def to_messages(system: str, history: list[ChatTurn], user: str) -> list[BaseMessage]:
        messages: list[BaseMessage] = [SystemMessage(system)]
        for turn in history:
            messages.append(HumanMessage(turn.content) if turn.role == "user" else AIMessage(turn.content))
        messages.append(HumanMessage(user))
        return messages

    async def structured(self, schema: type[T], system: str, user: str, history: list[ChatTurn] | None = None) -> T:
        """Ask the model for an answer in the shape of `schema` (a Pydantic model)."""
        runnable = self.chat_model.with_structured_output(schema)
        messages = self.to_messages(system, history or [], user)
        started = time.perf_counter()
        try:
            async with self._semaphore:
                async for attempt in AsyncRetrying(
                    retry=retry_if_exception_type(RETRYABLE),
                    stop=stop_after_attempt(self.max_retries + 1),
                    wait=wait_exponential(multiplier=self.retry_base_seconds, min=self.retry_base_seconds, max=30),
                    before_sleep=self._log_retry,
                    reraise=True,
                ):
                    with attempt:
                        result = await runnable.ainvoke(messages)
        except RETRYABLE as exc:
            log_event(logger, "error", level=logging.ERROR, kind="llm_unavailable", detail=type(exc).__name__)
            raise LLMUnavailableError(type(exc).__name__) from exc
        log_event(logger, "llm_call", schema=schema.__name__, ms=round((time.perf_counter() - started) * 1000))
        return result

    @staticmethod
    def _log_retry(state) -> None:
        log_event(
            logger, "retry", level=logging.WARNING, service="openai",
            attempt=state.attempt_number, detail=type(state.outcome.exception()).__name__,
        )
