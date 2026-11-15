"""Transporte do provedor opcional Notaas (platform.notaas.com.br).

Este modulo concentra a comunicacao HTTP com a API v1 da Notaas para NFS-e
(cobertura de 5.570 municipios, consulta de status, emissao e cancelamento).

Comportamento opt-in:
- A consulta de cobertura municipal (``/api/v1/cobertura/cidades``) e publica e
  gratuita (nao exige chave de API).
- As operacoes autenticadas de NFS-e (consulta por ``invoice_id``, emissao e
  cancelamento) so entram em acao quando ``NOTAAS_API_KEY`` esta configurado;
  sem chave, o servidor segue usando exclusivamente as fontes gratuitas padrao.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from aiolimiter import AsyncLimiter

from mcp_fiscal_brasil._core import (
    FiscalHTTPError,
    HTTPClient,
    get_logger,
    settings,
)

logger = get_logger(__name__)

# Teto compartilhado de requisicoes por segundo para a API da Notaas.
NOTAAS_MAX_REQUISICOES_POR_SEGUNDO = 10

_INVOICE_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")

_limiter: AsyncLimiter | None = None


def _get_limiter() -> AsyncLimiter:
    """Retorna o limitador unico (singleton de modulo) compartilhado pela API."""
    global _limiter
    if _limiter is None:
        _limiter = AsyncLimiter(
            NOTAAS_MAX_REQUISICOES_POR_SEGUNDO,
            NOTAAS_MAX_REQUISICOES_POR_SEGUNDO,
        )
    return _limiter


def provedor_configurado() -> bool:
    """Indica se o provedor opcional Notaas esta habilitado (NOTAAS_API_KEY definido)."""
    return bool(settings.notaas_api_key.strip())


def _http_client(
    *,
    cache_ttl: int | None = None,
    max_retries: int | None = None,
) -> HTTPClient:
    """Instancia o cliente HTTP configurado para a API da Notaas com limitador compartilhado."""
    return HTTPClient(
        settings.notaas_base_url,
        timeout=settings.mcp_fiscal_http_timeout,
        max_retries=(settings.mcp_fiscal_max_retries if max_retries is None else max_retries),
        cache_ttl=settings.mcp_fiscal_cache_ttl if cache_ttl is None else cache_ttl,
        rate_limit_per_second=NOTAAS_MAX_REQUISICOES_POR_SEGUNDO,
        limiter=_get_limiter(),
    )


def _auth_headers() -> dict[str, str]:
    """Monta o cabeçalho de autenticação x-api-key ou levanta FiscalHTTPError se ausente."""
    token = settings.notaas_api_key.strip()
    if not token:
        raise FiscalHTTPError(
            "Provedor Notaas nao configurado (NOTAAS_API_KEY ausente).",
            status_code=0,
            url=settings.notaas_base_url,
        )
    return {"x-api-key": token}


async def consultar_cobertura_cidades(
    *,
    q: str | None = None,
    uf: str | None = None,
    ibge: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Consulta a cobertura municipal de NFS-e na base publica da Notaas (5.570 municipios).

    Endpoint publico (nao requer ``NOTAAS_API_KEY``): ``GET /api/v1/cobertura/cidades``.
    Retorna codigo IBGE, codigo TOM, engine municipal ativa (snnfse, sp_prefeitura,
    ginfes, betha, issnet, etc.) e status de adesao ao SNNFSE/ADN Nacional.
    """
    params: dict[str, Any] = {"limit": max(1, min(limit, 50))}
    if q and q.strip():
        params["q"] = q.strip()
    if uf and uf.strip():
        params["uf"] = uf.strip().upper()
    if ibge and ibge.strip():
        params["ibge"] = ibge.strip()

    headers: dict[str, str] | None = None
    if provedor_configurado():
        headers = {"x-api-key": settings.notaas_api_key.strip()}

    async with _http_client() as client:
        return await client.get("/api/v1/cobertura/cidades", params=params, headers=headers)


def validar_invoice_id(invoice_id: str) -> str:
    """Valida e normaliza um identificador de invoice (apenas letras, dígitos, '_' e '-')."""
    id_limpo = invoice_id.strip()
    if not id_limpo:
        raise ValueError("invoice_id é obrigatório")
    if not _INVOICE_ID_RE.fullmatch(id_limpo):
        raise ValueError("invoice_id inválido: use apenas letras, números, '_' e '-'")
    return id_limpo


async def consultar_status_nfse(invoice_id: str) -> dict[str, Any]:
    """Consulta o status e dados de uma NFS-e na Notaas pelo ID da invoice.

    Requer ``NOTAAS_API_KEY`` configurado. A chave trafega exclusivamente no
    header ``x-api-key``, nunca na URL nem em mensagens de erro.
    """
    headers = _auth_headers()
    id_limpo = validar_invoice_id(invoice_id)

    segmento = quote(id_limpo, safe="")
    async with _http_client(cache_ttl=0) as client:
        return await client.get(f"/api/v1/invoices/{segmento}/status", headers=headers)


async def emitir_nfse(payload: dict[str, Any]) -> dict[str, Any]:
    """Enfileira a emissao de uma NFS-e via API v1 da Notaas (POST /api/v1/emitir).

    Requer ``NOTAAS_API_KEY`` configurado.
    """
    headers = _auth_headers()
    async with _http_client(cache_ttl=0, max_retries=1) as client:
        return await client.post("/api/v1/emitir", json=payload, headers=headers)


async def cancelar_nfse(
    invoice_id: str,
    motivo: str | None = None,
    codigo_cancelamento: str | None = None,
) -> dict[str, Any]:
    """Solicita o cancelamento de uma NFS-e emitida via Notaas (POST /api/v1/cancelar).

    Requer ``NOTAAS_API_KEY`` configurado.
    """
    headers = _auth_headers()
    id_limpo = validar_invoice_id(invoice_id)

    body: dict[str, Any] = {"invoiceId": id_limpo}
    if motivo and motivo.strip():
        body["motivo"] = motivo.strip()
    if codigo_cancelamento and codigo_cancelamento.strip():
        body["codigoCancelamento"] = codigo_cancelamento.strip()

    async with _http_client(cache_ttl=0, max_retries=1) as client:
        return await client.post("/api/v1/cancelar", json=body, headers=headers)


__all__ = [
    "NOTAAS_MAX_REQUISICOES_POR_SEGUNDO",
    "cancelar_nfse",
    "consultar_cobertura_cidades",
    "consultar_status_nfse",
    "emitir_nfse",
    "provedor_configurado",
    "validar_invoice_id",
]
