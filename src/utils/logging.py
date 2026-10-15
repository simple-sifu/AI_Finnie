"""Shared logging setup for Finnie (Story 1.6, architecture §13).

Call `setup_logging(settings)` once at start-up. Every module then logs with
`get_logger(__name__)` and records structured events with `log_event`.

Secrets are masked on the handlers, so the masking applies to every log line,
including those from third-party libraries such as httpx, which logs request
URLs that contain API keys.
"""

from __future__ import annotations

import contextvars
import logging
import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
MASK = "****"

# Libraries that log too much at INFO, including full request URLs.
NOISY_LOGGERS = ("httpx", "httpx2", "httpcore", "openai", "urllib3", "sentence_transformers", "faiss")

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Masks API keys passed in URLs or key=value text, and OpenAI-style keys.
_PATTERNS = [
    re.compile(r"(?i)\b(api_?key|apikey|token|secret)=([^&\s\"']+)"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
]


class SecretRedactor(logging.Filter):
    """Masks registered secret values and key-like patterns in every record."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets: set[str] = set()

    def register(self, values: Iterable[str | None]) -> None:
        # Very short values are ignored so common words are never masked by accident.
        self._secrets.update(v for v in values if v and len(v) >= 6)

    def redact(self, text: str) -> str:
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, MASK)
        text = _PATTERNS[0].sub(lambda m: f"{m.group(1)}={MASK}", text)
        return _PATTERNS[1].sub(MASK, text)

    def filter(self, record: logging.LogRecord) -> bool:
        message = self.redact(record.getMessage())
        record.msg, record.args = message, None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        return True


class RequestIdFilter(logging.Filter):
    """Adds the current request ID (or "-") to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


redactor = SecretRedactor()


def setup_logging(
    level: str = "INFO",
    secrets: Iterable[str | None] = (),
    log_dir: Path | None = DEFAULT_LOG_DIR,
    console: bool = True,
) -> None:
    """Configure the root logger once. Calling it again replaces Finnie's handlers."""
    redactor.register(secrets)
    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, "_finnie", False)]:
        root.removeHandler(handler)
        handler.close()

    handlers: list[logging.Handler] = []
    if console:
        handlers.append(logging.StreamHandler())
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(log_dir / "finnie.log", maxBytes=1_000_000, backupCount=3)
        )

    for handler in handlers:
        handler._finnie = True  # type: ignore[attr-defined]
        handler.addFilter(RequestIdFilter())
        handler.addFilter(redactor)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)

    root.setLevel(level.upper())
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def setup_logging_from_settings(settings: Any, **kwargs: Any) -> None:
    """Configure logging from loaded Settings and register its API keys for masking."""
    keys = settings.secrets
    secrets = [
        key.get_secret_value() if key is not None else None
        for key in (
            keys.openai_api_key,
            keys.alpha_vantage_api_key,
            keys.serpapi_api_key,
            keys.tavily_api_key,
        )
    ]
    setup_logging(settings.logging.level, secrets=secrets, **kwargs)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def request_context(request_id: str) -> Iterator[None]:
    """Tag every log line inside the block with a request ID."""
    token = _request_id.set(request_id)
    try:
        yield
    finally:
        _request_id.reset(token)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log a structured event as `event key=value ...`.

    Standard events (architecture §13): route, agent, api_call, cache, fallback, error.
    """
    parts = [event, *(f"{key}={_format(value)}" for key, value in fields.items())]
    logger.log(level, " ".join(parts))


def _format(value: Any) -> str:
    text = str(value)
    return f'"{text}"' if " " in text else text
