"""Story 1.6: shared logging setup."""

import logging

import httpx
import pytest

from src.core.config import load_settings
from src.utils import logging as finnie_logging
from src.utils.logging import (
    get_logger,
    log_event,
    request_context,
    setup_logging,
    setup_logging_from_settings,
)

KEYS = {
    "OPENAI_API_KEY": "sk-test-openai-123456",
    "ALPHA_VANTAGE_API_KEY": "AVKEY987654",
    "SERPAPI_API_KEY": "serpkey-abcdef",
}


@pytest.fixture
def log_dir(tmp_path):
    yield tmp_path
    # Leave the root logger clean for other tests.
    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, "_finnie", False)]:
        root.removeHandler(handler)
        handler.close()
    finnie_logging.redactor._secrets.clear()


def read_log(log_dir):
    for handler in logging.getLogger().handlers:
        handler.flush()
    return (log_dir / "finnie.log").read_text()


def test_writes_formatted_lines_to_file(log_dir):
    setup_logging("INFO", log_dir=log_dir, console=False)
    get_logger("src.test").info("hello")
    line = read_log(log_dir).strip()
    assert line.endswith("INFO src.test [-] hello")


def test_level_comes_from_settings(log_dir):
    settings = load_settings(
        environ={**KEYS, "FINNIE_LOGGING__LEVEL": "WARNING"}, config_path=log_dir / "none.yaml"
    )
    setup_logging_from_settings(settings, log_dir=log_dir, console=False)
    logger = get_logger("src.test")
    logger.info("hidden")
    logger.warning("shown")
    text = read_log(log_dir)
    assert "shown" in text and "hidden" not in text


def test_setup_twice_does_not_duplicate_handlers(log_dir):
    setup_logging("INFO", log_dir=log_dir, console=True)
    setup_logging("INFO", log_dir=log_dir, console=True)
    ours = [h for h in logging.getLogger().handlers if getattr(h, "_finnie", False)]
    assert len(ours) == 2


def test_registered_secrets_are_masked_everywhere(log_dir):
    settings = load_settings(environ=dict(KEYS), config_path=log_dir / "none.yaml")
    setup_logging_from_settings(settings, log_dir=log_dir, console=False)
    logger = get_logger("src.test")
    logger.info("using key %s", KEYS["SERPAPI_API_KEY"])
    log_event(logger, "api_call", detail=f"key {KEYS['OPENAI_API_KEY']}")
    try:
        raise RuntimeError(f"failed with {KEYS['ALPHA_VANTAGE_API_KEY']}")
    except RuntimeError:
        logger.exception("request failed")
    text = read_log(log_dir)
    for value in KEYS.values():
        assert value not in text
    assert "****" in text


def test_key_patterns_are_masked_even_if_not_registered(log_dir):
    setup_logging("INFO", log_dir=log_dir, console=False)
    get_logger("src.test").info(
        "GET https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey=UNREGISTERED1 "
        "and serpapi api_key=OTHERSECRET and sk-abcdefghijk"
    )
    text = read_log(log_dir)
    assert "UNREGISTERED1" not in text and "OTHERSECRET" not in text and "sk-abcdefghijk" not in text
    assert "symbol=SPY" in text  # ordinary values are left alone


def test_short_values_are_not_registered_as_secrets(log_dir):
    setup_logging("INFO", secrets=["SPY", None, ""], log_dir=log_dir, console=False)
    get_logger("src.test").info("ticker SPY")
    assert "ticker SPY" in read_log(log_dir)


def test_third_party_url_logs_are_masked(log_dir):
    setup_logging("DEBUG", secrets=[KEYS["ALPHA_VANTAGE_API_KEY"]], log_dir=log_dir, console=False)
    url = f"https://www.alphavantage.co/query?symbol=SPY&apikey={KEYS['ALPHA_VANTAGE_API_KEY']}"
    logging.getLogger("httpx").warning("HTTP Request: GET %s", httpx.URL(url))
    text = read_log(log_dir)
    assert KEYS["ALPHA_VANTAGE_API_KEY"] not in text and "apikey=****" in text


def test_noisy_libraries_are_quieted(log_dir):
    setup_logging("DEBUG", log_dir=log_dir, console=False)
    assert logging.getLogger("httpx").level == logging.WARNING


def test_request_id_is_added_inside_context(log_dir):
    setup_logging("INFO", log_dir=log_dir, console=False)
    logger = get_logger("src.test")
    with request_context("req-42"):
        logger.info("inside")
    logger.info("outside")
    text = read_log(log_dir)
    assert "[req-42] inside" in text and "[-] outside" in text


def test_log_event_formats_fields(log_dir):
    setup_logging("INFO", log_dir=log_dir, console=False)
    log_event(get_logger("src.test"), "route", agent="market", confidence=0.92, note="two words")
    assert 'route agent=market confidence=0.92 note="two words"' in read_log(log_dir)


def test_log_event_respects_level(log_dir):
    setup_logging("INFO", log_dir=log_dir, console=False)
    log_event(get_logger("src.test"), "error", level=logging.ERROR, kind="timeout")
    assert "ERROR src.test [-] error kind=timeout" in read_log(log_dir)


def test_no_log_dir_means_console_only(log_dir):
    setup_logging("INFO", log_dir=None, console=True)
    ours = [h for h in logging.getLogger().handlers if getattr(h, "_finnie", False)]
    assert len(ours) == 1 and not (log_dir / "finnie.log").exists()


def test_secrets_are_masked_in_a_traceback_even_when_it_is_formatted_later():
    import sys

    finnie_logging.redactor.register(["supersecret-key-123"])
    try:
        raise RuntimeError("failed with supersecret-key-123")
    except RuntimeError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "request failed", None, sys.exc_info())
    assert finnie_logging.redactor.filter(record)
    assert "supersecret-key-123" not in record.exc_text and "Traceback" in record.exc_text and "****" in record.exc_text
    finnie_logging.redactor._secrets.discard("supersecret-key-123")
