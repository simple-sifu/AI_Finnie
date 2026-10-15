"""Story 1.5: configuration management."""

from pathlib import Path

import pytest

from src.core import config
from src.core.config import ConfigError, load_settings

ROOT = Path(__file__).resolve().parents[2]

KEYS = {
    "OPENAI_API_KEY": "sk-test-openai-123456",
    "ALPHA_VANTAGE_API_KEY": "av-test-key-123456",
    "SERPAPI_API_KEY": "serp-test-key-123456",
}


def write_yaml(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return path


def test_defaults_load_with_only_required_keys(tmp_path):
    settings = load_settings(config_path=tmp_path / "missing.yaml", environ=dict(KEYS))
    assert settings.llm.model == "gpt-4o-mini"
    assert settings.market.quote_ttl_seconds == 1800
    assert settings.market.mode == "live"
    assert settings.news.provider == "serpapi"
    assert settings.secrets.tavily_api_key is None


def test_project_config_yaml_is_valid():
    settings = load_settings(config_path=ROOT / "config.yaml", environ=dict(KEYS))
    assert settings.market.tickers == ["SPY", "QQQ", "DIA", "VTI", "BND"]
    assert "not personalized" in settings.disclaimer.text


def test_yaml_values_are_used(tmp_path):
    path = write_yaml(tmp_path, "market:\n  daily_limit: 10\n  tickers: [spy, qqq, dia]\n")
    settings = load_settings(config_path=path, environ=dict(KEYS))
    assert settings.market.daily_limit == 10
    assert settings.market.tickers == ["SPY", "QQQ", "DIA"]


def test_named_env_vars_override_yaml(tmp_path):
    path = write_yaml(tmp_path, "llm:\n  model: from-yaml\nmarket:\n  mode: live\n")
    env = {
        **KEYS,
        "OPENAI_MODEL": "gpt-4o-mini",
        "MARKET_DATA_MODE": "mock",
        "QUOTE_CACHE_TTL_SECONDS": "600",
    }
    settings = load_settings(config_path=path, environ=env)
    assert settings.llm.model == "gpt-4o-mini"
    assert settings.market.mode == "mock"
    assert settings.market.quote_ttl_seconds == 600


def test_prefixed_env_vars_override_any_setting(tmp_path):
    path = write_yaml(tmp_path, "chat:\n  history_turns: 10\n")
    env = {**KEYS, "FINNIE_CHAT__HISTORY_TURNS": "4", "FINNIE_ROUTER__MIN_CONFIDENCE": "0.7"}
    settings = load_settings(config_path=path, environ=env)
    assert settings.chat.history_turns == 4
    assert settings.router.min_confidence == 0.7


@pytest.mark.parametrize("missing", list(KEYS))
def test_missing_required_key_names_the_key(tmp_path, missing):
    env = {name: value for name, value in KEYS.items() if name != missing}
    with pytest.raises(ConfigError, match=missing):
        load_settings(config_path=tmp_path / "missing.yaml", environ=env)


def test_blank_key_counts_as_missing(tmp_path):
    env = {**KEYS, "SERPAPI_API_KEY": "   "}
    with pytest.raises(ConfigError, match="SERPAPI_API_KEY"):
        load_settings(config_path=tmp_path / "missing.yaml", environ=env)


def test_tavily_key_required_only_when_tavily_is_the_provider(tmp_path):
    path = write_yaml(tmp_path, "news:\n  provider: tavily\n")
    with pytest.raises(ConfigError, match="TAVILY_API_KEY"):
        load_settings(config_path=path, environ=dict(KEYS))
    settings = load_settings(config_path=path, environ={**KEYS, "TAVILY_API_KEY": "tv-key-123"})
    assert settings.secrets.tavily_api_key.get_secret_value() == "tv-key-123"


def test_keys_in_yaml_are_ignored(tmp_path):
    path = write_yaml(tmp_path, "secrets:\n  openai_api_key: from-yaml\n")
    settings = load_settings(config_path=path, environ=dict(KEYS))
    assert settings.secrets.openai_api_key.get_secret_value() == KEYS["OPENAI_API_KEY"]


def test_secrets_never_appear_in_text_output(tmp_path):
    settings = load_settings(config_path=tmp_path / "missing.yaml", environ=dict(KEYS))
    text = f"{settings} {settings!r} {settings.secrets} {settings.model_dump()}"
    for value in KEYS.values():
        assert value not in text


def test_invalid_values_give_a_readable_error(tmp_path):
    path = write_yaml(tmp_path, "market:\n  tickers: [SPY, QQQ]\n  mode: sometimes\n")
    with pytest.raises(ConfigError) as error:
        load_settings(config_path=path, environ=dict(KEYS))
    message = str(error.value)
    assert "market.tickers" in message and "market.mode" in message
    for value in KEYS.values():
        assert value not in message


def test_invalid_yaml_is_reported(tmp_path):
    path = write_yaml(tmp_path, "market: [unclosed\n")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_settings(config_path=path, environ=dict(KEYS))


def test_yaml_must_be_a_mapping(tmp_path):
    path = write_yaml(tmp_path, "- just\n- a list\n")
    with pytest.raises(ConfigError, match="must contain sections"):
        load_settings(config_path=path, environ=dict(KEYS))


def test_env_example_lists_every_key():
    example = (ROOT / ".env.example").read_text()
    for name in [*KEYS, "TAVILY_API_KEY", "OPENAI_MODEL", "MARKET_DATA_MODE", "QUOTE_CACHE_TTL_SECONDS"]:
        assert f"{name}=" in example


def test_env_file_is_gitignored():
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in ignored and "!.env.example" in ignored


def test_cli_reports_ok(monkeypatch, capsys):
    monkeypatch.setattr(config, "load_settings", lambda: load_settings(environ=dict(KEYS)))
    assert config.main() == 0
    assert "Configuration OK" in capsys.readouterr().out


def test_cli_reports_missing_key(monkeypatch, capsys):
    def fail():
        raise ConfigError("Missing required setting(s): OPENAI_API_KEY.")

    monkeypatch.setattr(config, "load_settings", fail)
    assert config.main() == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_load_settings_reads_env_file(tmp_path, monkeypatch):
    # Give load_dotenv a throwaway environment so test keys don't leak into the process.
    monkeypatch.setattr(config.os, "environ", {})
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(f"{name}={value}" for name, value in KEYS.items()))
    settings = load_settings(config_path=tmp_path / "missing.yaml", env_file=env_file)
    assert settings.secrets.serpapi_api_key.get_secret_value() == KEYS["SERPAPI_API_KEY"]


def test_rag_settings_load_without_any_keys(tmp_path):
    from src.core.config import load_rag_settings

    path = write_yaml(tmp_path, "rag:\n  chunk_chars: 600\n")
    rag = load_rag_settings(config_path=path, environ={"FINNIE_RAG__TOP_K": "6"})
    assert rag.chunk_chars == 600 and rag.top_k == 6


def test_invalid_rag_settings_are_reported(tmp_path):
    from src.core.config import load_rag_settings

    path = write_yaml(tmp_path, "rag:\n  chunk_chars: 10\n")
    with pytest.raises(ConfigError, match="rag.chunk_chars"):
        load_rag_settings(config_path=path, environ={})
