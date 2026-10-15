"""Disclaimer policy (FR28, D-7, D-43, architecture §7.4).

Finnie may give advice, but every advice-type response carries a disclaimer.
When it's uncertain whether a response is advice, it is treated as advice.
Education-only responses carry none. Applying the policy twice is harmless.
"""

from __future__ import annotations

from src.core.models import AgentResponse


def apply_disclaimer(response: AgentResponse, text: str) -> AgentResponse:
    if response.error or not response.is_advice:
        return response.model_copy(update={"disclaimer": None})
    return response.model_copy(update={"disclaimer": text})
