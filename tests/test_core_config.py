"""Tests for environment driven settings."""

from pathlib import Path

from mcp_fiscal_brasil._core.config import Settings


def test_settings_defaults_load_without_env_file() -> None:
    settings = Settings(_env_file=None)

    assert settings.mcp_fiscal_env == "development"
    assert settings.mcp_fiscal_log_level == "INFO"
    assert settings.mcp_fiscal_cache_ttl == 300
    assert settings.mcp_fiscal_rate_limit == 10
    assert settings.mcp_fiscal_http_timeout == 30.0
    assert settings.mcp_fiscal_max_retries == 3
    assert settings.mcp_fiscal_file_base_dir == "~/.local/share/mcp-fiscal-brasil/files"
    assert settings.brasilapi_base_url == "https://brasilapi.com.br/api"
    assert settings.receita_base_url == "https://receitaws.com.br/v1"


def test_settings_env_vars_override_defaults(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MCP_FISCAL_ENV", "production")
    monkeypatch.setenv("MCP_FISCAL_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MCP_FISCAL_CACHE_TTL", "60")
    monkeypatch.setenv("MCP_FISCAL_RATE_LIMIT", "3")
    monkeypatch.setenv("MCP_FISCAL_HTTP_TIMEOUT", "5.5")
    monkeypatch.setenv("MCP_FISCAL_MAX_RETRIES", "4")
    monkeypatch.setenv("MCP_FISCAL_FILE_BASE_DIR", "/tmp/fiscal-inputs")
    monkeypatch.setenv("BRASILAPI_BASE_URL", "https://brasilapi.example.test")
    monkeypatch.setenv("RECEITA_BASE_URL", "https://receita.example.test")

    settings = Settings(_env_file=None)

    assert settings.mcp_fiscal_env == "production"
    assert settings.mcp_fiscal_log_level == "DEBUG"
    assert settings.mcp_fiscal_cache_ttl == 60
    assert settings.mcp_fiscal_rate_limit == 3
    assert settings.mcp_fiscal_http_timeout == 5.5
    assert settings.mcp_fiscal_max_retries == 4
    assert settings.mcp_fiscal_file_base_dir == "/tmp/fiscal-inputs"
    assert settings.brasilapi_base_url == "https://brasilapi.example.test"
    assert settings.receita_base_url == "https://receita.example.test"


def test_settings_env_file_is_respected(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "MCP_FISCAL_ENV=production",
                "MCP_FISCAL_LOG_LEVEL=WARNING",
                "MCP_FISCAL_CACHE_TTL=120",
                "MCP_FISCAL_RATE_LIMIT=7",
                "MCP_FISCAL_HTTP_TIMEOUT=9.5",
                "MCP_FISCAL_MAX_RETRIES=5",
                "MCP_FISCAL_FILE_BASE_DIR=/tmp/fiscal-env-inputs",
                "BRASILAPI_BASE_URL=https://brasilapi.env.test",
                "RECEITA_BASE_URL=https://receita.env.test",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.mcp_fiscal_env == "production"
    assert settings.mcp_fiscal_log_level == "WARNING"
    assert settings.mcp_fiscal_cache_ttl == 120
    assert settings.mcp_fiscal_rate_limit == 7
    assert settings.mcp_fiscal_http_timeout == 9.5
    assert settings.mcp_fiscal_max_retries == 5
    assert settings.mcp_fiscal_file_base_dir == "/tmp/fiscal-env-inputs"
    assert settings.brasilapi_base_url == "https://brasilapi.env.test"
    assert settings.receita_base_url == "https://receita.env.test"
