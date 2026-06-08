"""Application configuration for mcp-fiscal-brasil."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    mcp_fiscal_env: str = "development"
    mcp_fiscal_log_level: str = "INFO"
    mcp_fiscal_cache_ttl: int = 300
    mcp_fiscal_rate_limit: int = 10
    mcp_fiscal_http_timeout: float = 30.0
    mcp_fiscal_max_retries: int = 3
    mcp_fiscal_file_base_dir: str = "~/.local/share/mcp-fiscal-brasil/files"
    brasilapi_base_url: str = "https://brasilapi.com.br/api"
    receita_base_url: str = "https://receitaws.com.br/v1"
    ibge_cnae_base_url: str = "https://servicodados.ibge.gov.br/api/v2/cnae"
    ibge_localidades_base_url: str = "https://servicodados.ibge.gov.br/api/v1/localidades"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

__all__ = ["Settings", "settings"]
