"""Finnie settings: config.yaml plus environment variables (Story 1.5, D-25).

Precedence, highest first:
1. Real environment variables
2. Variables in the .env file
3. config.yaml
4. Defaults in this module

Secrets (API keys) come only from the environment, never from config.yaml.
Any config.yaml setting can be overridden with FINNIE_<SECTION>__<KEY>,
for example FINNIE_MARKET__DAILY_LIMIT=10.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PREFIX = "FINNIE_"

# Environment variables with their own names (documented in .env.example).
REQUIRED_SECRETS = ("OPENAI_API_KEY", "ALPHA_VANTAGE_API_KEY", "SERPAPI_API_KEY")
NAMED_ENV_OVERRIDES = {
    "OPENAI_MODEL": ("llm", "model"),
    "MARKET_DATA_MODE": ("market", "mode"),
    "QUOTE_CACHE_TTL_SECONDS": ("market", "quote_ttl_seconds"),
}


class ConfigError(Exception):
    """Raised when settings are missing or invalid. The message is safe to show users."""


class LLMSettings(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = Field(0.2, ge=0, le=2)
    timeout_s: float = Field(30, gt=0)
    max_concurrent: int = Field(4, ge=1)
    max_retries: int = Field(3, ge=0)


class ChatSettings(BaseModel):
    history_turns: int = Field(10, ge=1)
    max_input_chars: int = Field(2000, ge=1)
    timeout_s: float = Field(90, gt=0)  # one whole chat answer, router and agent together


class RouterSettings(BaseModel):
    min_confidence: float = Field(0.5, ge=0, le=1)


class RAGSettings(BaseModel):
    chunk_chars: int = Field(800, ge=100)
    chunk_overlap: int = Field(100, ge=0)
    top_k: int = Field(4, ge=1)
    min_score: float = Field(0.35, ge=-1, le=1)


class MarketSettings(BaseModel):
    mode: Literal["live", "mock"] = "live"
    tickers: list[str] = ["SPY", "QQQ", "DIA", "VTI", "BND"]
    quote_ttl_seconds: int = Field(1800, ge=0)
    history_ttl_seconds: int = Field(86400, ge=0)
    daily_limit: int = Field(25, ge=0)
    per_minute_limit: int = Field(5, ge=0)
    min_interval_seconds: float = Field(1.5, ge=0)  # Alpha Vantage burst limit (architecture §9.1)
    max_retries: int = Field(3, ge=0)

    @field_validator("tickers")
    @classmethod
    def three_to_five_tickers(cls, value: list[str]) -> list[str]:
        if not 3 <= len(value) <= 5:
            raise ValueError("market.tickers must list 3 to 5 tickers (PRD D-18)")
        return [ticker.upper() for ticker in value]


class NewsSettings(BaseModel):
    provider: Literal["serpapi", "tavily"] = "serpapi"
    ttl_seconds: int = Field(21600, ge=0)
    monthly_limit: int = Field(100, ge=0)


class GoalSettings(BaseModel):
    annual_return: dict[Literal["conservative", "moderate", "aggressive"], float] = {
        "conservative": 0.03,
        "moderate": 0.05,
        "aggressive": 0.07,
    }


class PortfolioSettings(BaseModel):
    max_rows: int = Field(200, ge=1)
    max_file_mb: float = Field(1, gt=0)


class DisclaimerSettings(BaseModel):
    text: str = (
        "This is general information for learning purposes, not personalized financial, "
        "investment or tax advice. Consider speaking with a licensed professional before "
        "making decisions."
    )


class LoggingSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class Secrets(BaseModel):
    """API keys. SecretStr keeps them out of logs, reprs and error messages."""

    openai_api_key: SecretStr
    alpha_vantage_api_key: SecretStr
    serpapi_api_key: SecretStr
    tavily_api_key: SecretStr | None = None


class Settings(BaseModel):
    llm: LLMSettings = LLMSettings()
    chat: ChatSettings = ChatSettings()
    router: RouterSettings = RouterSettings()
    rag: RAGSettings = RAGSettings()
    market: MarketSettings = MarketSettings()
    news: NewsSettings = NewsSettings()
    goals: GoalSettings = GoalSettings()
    portfolio: PortfolioSettings = PortfolioSettings()
    disclaimer: DisclaimerSettings = DisclaimerSettings()
    logging: LoggingSettings = LoggingSettings()
    secrets: Secrets


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must contain sections such as 'llm:' and 'market:'")
    return data


def _set(data: dict[str, Any], section: str, key: str, raw: str) -> None:
    # yaml.safe_load turns "10" into 10, "true" into True, "[A, B]" into a list.
    data.setdefault(section, {})[key] = yaml.safe_load(raw)


def _apply_env_overrides(data: dict[str, Any], env: dict[str, str]) -> None:
    for name, (section, key) in NAMED_ENV_OVERRIDES.items():
        if env.get(name):
            _set(data, section, key, env[name])
    for name, raw in env.items():
        if name.startswith(ENV_PREFIX) and "__" in name:
            section, key = name[len(ENV_PREFIX):].lower().split("__", 1)
            _set(data, section, key, raw)


def _read_secrets(env: dict[str, str], provider: str) -> dict[str, str]:
    required = list(REQUIRED_SECRETS)
    if provider == "tavily":
        required.append("TAVILY_API_KEY")
    missing = [name for name in required if not env.get(name, "").strip()]
    if missing:
        raise ConfigError(
            f"Missing required setting(s): {', '.join(missing)}. "
            "Add them to your .env file (see .env.example)."
        )
    secrets = {name.lower(): env[name].strip() for name in required}
    if env.get("TAVILY_API_KEY", "").strip():
        secrets["tavily_api_key"] = env["TAVILY_API_KEY"].strip()
    return secrets


def _describe(error: ValidationError) -> str:
    problems = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        problems.append(f"{location}: {item['msg']}")
    return "Invalid settings: " + "; ".join(problems)


def _load_data(
    config_path: Path | None, env_file: Path | None, environ: dict[str, str] | None
) -> tuple[dict[str, Any], dict[str, str]]:
    config_path = config_path or PROJECT_ROOT / "config.yaml"
    if environ is None:
        load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
        environ = dict(os.environ)
    data = _read_yaml(config_path)
    data.pop("secrets", None)  # keys may only come from the environment
    _apply_env_overrides(data, environ)
    return data, environ


def load_settings(
    config_path: Path | None = None,
    env_file: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Settings:
    """Load and validate settings. Raises ConfigError with a user-safe message."""
    data, environ = _load_data(config_path, env_file, environ)

    provider = str((data.get("news") or {}).get("provider", "serpapi"))
    data["secrets"] = _read_secrets(environ, provider)

    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(_describe(exc)) from None


def load_rag_settings(
    config_path: Path | None = None,
    env_file: Path | None = None,
    environ: dict[str, str] | None = None,
) -> RAGSettings:
    """Load only the rag: section. Used by the index build, which needs no API keys."""
    data, _ = _load_data(config_path, env_file, environ)
    try:
        return RAGSettings.model_validate(data.get("rag") or {})
    except ValidationError as exc:
        raise ConfigError(_describe(exc).replace("Invalid settings: ", "Invalid settings: rag.")) from None


def main() -> int:
    """`python -m src.core.config` checks the configuration without starting the app."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    print(
        f"Configuration OK: model={settings.llm.model}, market mode={settings.market.mode}, "
        f"news provider={settings.news.provider}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
