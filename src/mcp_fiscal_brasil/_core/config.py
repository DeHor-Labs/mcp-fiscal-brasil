"""Application configuration for mcp-fiscal-brasil."""

from pydantic import field_validator
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

    # Provedor premium opcional cpfcnpj.com.br (opt-in). Sem token configurado, o
    # servico opera exatamente como antes, usando apenas as fontes gratuitas. Ao
    # definir CPFCNPJ_TOKEN, as consultas de CNPJ (pacotes 5/6) e de NF-e/NFC-e por
    # chave (pacotes 100/102) passam a tentar primeiro a cpfcnpj.com.br, com dados
    # oficiais em tempo real, e mantem as fontes gratuitas como fallback.
    cpfcnpj_token: str = ""
    cpfcnpj_base_url: str = "https://api.cpfcnpj.com.br"
    # Timeout dedicado da cpfcnpj.com.br. A documentacao do provedor recomenda 60s:
    # com um valor menor a requisicao pode ser cortada depois de o credito ja ter
    # sido consumido. Nao afeta o timeout global das fontes gratuitas.
    cpfcnpj_timeout: float = 60.0
    cpfcnpj_cnpj_packet: int = 6
    # Pacote de CPF usado por consultar_cpf. Padrao 26 (CPF D Simplificado): nome,
    # nascimento e situacao cadastral, o mais barato que traz situacao. Aceita
    # 1 (so nome), 3 (nome, nascimento, genero e endereco), 8 (situacao + motivo,
    # ano de obito, numero e PDF do comprovante) e 26.
    cpfcnpj_cpf_packet: int = 26
    ibge_cnae_base_url: str = "https://servicodados.ibge.gov.br/api/v2/cnae"
    ibge_localidades_base_url: str = "https://servicodados.ibge.gov.br/api/v1/localidades"
    bcb_sgs_base_url: str = "https://api.bcb.gov.br/dados/serie"

    # Certificado digital A1 (e-CNPJ) para consultas mTLS aos webservices SEFAZ
    # (status de servico, distribuicao, manifestacao). Configurado via secret/volume
    # montado no deploy (Cloud Run --set-secrets, Fly.io secrets ou volume Docker),
    # nunca em texto plano no .env de producao.
    nfe_certificado_path: str = ""
    nfe_certificado_senha: str = ""
    nfe_emitente_cnpj: str = ""
    nfe_ambiente: str = "producao"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("cpfcnpj_base_url")
    @classmethod
    def _exigir_https_cpfcnpj(cls, valor: str) -> str:
        """Exige HTTPS na base da cpfcnpj.com.br.

        O token da conta viaja no caminho da URL (``/{token}/{pacote}/{documento}``),
        portanto a base nao pode usar ``http://``, mesmo quando sobrescrita por
        variavel de ambiente, sob pena de expor o token sem criptografia.
        """
        normalizado = valor.strip()
        if not normalizado.lower().startswith("https://"):
            raise ValueError(
                "CPFCNPJ_BASE_URL deve usar https:// (o token da conta viaja no "
                "caminho da URL e nao pode trafegar sem criptografia)."
            )
        return normalizado

    @field_validator("cpfcnpj_timeout")
    @classmethod
    def _validar_timeout_cpfcnpj(cls, valor: float) -> float:
        """Garante um timeout positivo para o provedor premium."""
        if valor <= 0:
            raise ValueError(f"CPFCNPJ_TIMEOUT deve ser maior que zero (recebido: {valor}).")
        return valor

    @field_validator("cpfcnpj_cpf_packet")
    @classmethod
    def _validar_pacote_cpf(cls, valor: int) -> int:
        """Restringe o pacote de CPF aos niveis suportados por consultar_cpf.

        Apenas os pacotes com uso fiscal claro sao aceitos: 1 (so nome), 3 (nome,
        nascimento, genero e endereco), 8 (situacao completa com PDF do comprovante)
        e 26 (situacao simplificada). Um valor fora disso e um erro de configuracao.
        """
        pacotes_validos = {1, 3, 8, 26}
        if valor not in pacotes_validos:
            aceitos = ", ".join(str(p) for p in sorted(pacotes_validos))
            raise ValueError(f"CPFCNPJ_CPF_PACKET deve ser um de: {aceitos} (recebido: {valor}).")
        return valor


settings = Settings()

__all__ = ["Settings", "settings"]
