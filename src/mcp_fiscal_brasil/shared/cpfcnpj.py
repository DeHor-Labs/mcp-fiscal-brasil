"""Transporte do provedor premium opcional cpfcnpj.com.br.

Este modulo concentra a comunicacao HTTP com a API da cpfcnpj.com.br, usada de
forma opcional pelos clientes de CNPJ e de NF-e/NFC-e. O provedor so entra em
acao quando um token e configurado via ``CPFCNPJ_TOKEN``; sem token, os clientes
seguem usando exclusivamente as fontes gratuitas padrao.

Formato da chamada: ``GET {base}/{token}/{pacote}/{documento}``. A resposta traz
``status`` igual a 1 em caso de sucesso e igual a 0 em caso de erro, acompanhada
dos campos ``erro`` e ``erroCodigo``.
"""

from __future__ import annotations

from typing import Any

from aiolimiter import AsyncLimiter

from mcp_fiscal_brasil._core import (
    FiscalHTTPError,
    HTTPClient,
    get_logger,
    settings,
)

logger = get_logger(__name__)

# Pacotes de consulta na cpfcnpj.com.br.
PACOTE_NFE = 100
PACOTE_NFCE = 102

# Teto de requisicoes por segundo da cpfcnpj.com.br. Cada consulta abre um
# HTTPClient novo, entao o limitador precisa ser compartilhado por todas as
# instancias/chamadas: sem isso, consultas concorrentes (CNPJ pacotes 5/6 e
# NF-e/NFC-e pacotes 100/102) somariam limitadores independentes e poderiam
# ultrapassar o teto, recebendo o erro 1007 (HTTP 429).
CPFCNPJ_MAX_REQUISICOES_POR_SEGUNDO = 20

_limiter: AsyncLimiter | None = None


def _get_limiter() -> AsyncLimiter:
    """Retorna o limitador unico (singleton de modulo) compartilhado pela API."""
    global _limiter
    if _limiter is None:
        _limiter = AsyncLimiter(
            CPFCNPJ_MAX_REQUISICOES_POR_SEGUNDO,
            CPFCNPJ_MAX_REQUISICOES_POR_SEGUNDO,
        )
    return _limiter


def provedor_configurado() -> bool:
    """Indica se o provedor premium cpfcnpj.com.br esta habilitado (token definido)."""
    return bool(settings.cpfcnpj_token.strip())


def _http_client() -> HTTPClient:
    return HTTPClient(
        settings.cpfcnpj_base_url,
        timeout=settings.mcp_fiscal_http_timeout,
        max_retries=settings.mcp_fiscal_max_retries,
        cache_ttl=settings.mcp_fiscal_cache_ttl,
        rate_limit_per_second=CPFCNPJ_MAX_REQUISICOES_POR_SEGUNDO,
        limiter=_get_limiter(),
    )


async def consultar(pacote: int, documento: str) -> dict[str, Any]:
    """Consulta um documento na cpfcnpj.com.br e retorna o corpo JSON de sucesso.

    Args:
        pacote: Identificador do pacote de consulta (ex.: 6 para CNPJ, 100 para NF-e).
        documento: Documento consultado sem máscara (CNPJ numérico ou alfanumérico,
            CPF ou chave de acesso). O provedor aceita CNPJ alfanumérico no caminho da URL.

    Returns:
        dict com o corpo da resposta quando ``status`` e igual a 1.

    Raises:
        FiscalHTTPError: Quando o provedor nao esta configurado ou retorna erro
            (``status`` diferente de 1).
    """
    token = settings.cpfcnpj_token.strip()
    if not token:
        raise FiscalHTTPError(
            "Provedor cpfcnpj.com.br nao configurado (CPFCNPJ_TOKEN ausente).",
            status_code=0,
            url=settings.cpfcnpj_base_url,
        )

    path = f"/{token}/{pacote}/{documento}"
    async with _http_client() as client:
        data = await client.get(path)

    if data.get("status") != 1:
        codigo = data.get("erroCodigo")
        mensagem = data.get("erro") or "Consulta cpfcnpj.com.br sem sucesso."
        raise FiscalHTTPError(
            f"cpfcnpj.com.br retornou erro: {mensagem}",
            status_code=int(codigo) if isinstance(codigo, int) else 0,
            url=f"{settings.cpfcnpj_base_url}/***/{pacote}/{documento}",
            detail={"erro": mensagem, "erroCodigo": codigo},
        )

    return data


__all__ = [
    "PACOTE_NFCE",
    "PACOTE_NFE",
    "consultar",
    "provedor_configurado",
]
