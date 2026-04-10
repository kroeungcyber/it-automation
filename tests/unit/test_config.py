# tests/unit/test_config.py
import importlib
import pytest


def _load_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("LOCAL_MODEL", "gemma3:latest")
    monkeypatch.setenv("CLOUD_MODEL", "claude-sonnet-4-6")
    import src.config as cfg
    importlib.reload(cfg)
    return cfg.Settings()


def test_settings_load_from_env(monkeypatch):
    settings = _load_settings(monkeypatch)
    assert settings.database_url == "postgresql+asyncpg://u:p@localhost/db"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.anthropic_api_key == "sk-test"


def test_settings_log_level_default(monkeypatch):
    settings = _load_settings(monkeypatch)
    assert settings.log_level == "INFO"


def test_settings_model_defaults(monkeypatch):
    settings = _load_settings(monkeypatch)
    assert settings.local_model == "gemma3:latest"
    assert settings.cloud_model == "claude-sonnet-4-6"
