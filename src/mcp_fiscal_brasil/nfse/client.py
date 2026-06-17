"""
Cliente para a API Nacional NFS-e (Sistema Nacional NFS-e - adn.nfse.gov.br).

IMPORTANTE: A API Nacional exige certificado digital ICP-Brasil com mTLS.
Sem certificado configurado, todas as chamadas retornam None e a tool
cai automaticamente no fallback estático de portais municipais.

Referência: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# URL base da API de Dados Nacionais (ADN) em produção
_BASE_URL = "https://adn.nfse.gov.br"
# Timeout conservador: a API pode ser lenta
_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)


class NFSeNacionalClient:
    """
    Cliente para consulta de NFS-e na API Nacional (adn.nfse.gov.br).

    Retorna None em qualquer erro (auth, timeout, 404, rede) para que a
    camada superior possa acionar o fallback com orientações manuais.
    """

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    async def _get(self, path: str) -> dict[str, Any] | None:
        """Executa GET na API Nacional. Retorna None em qualquer falha."""
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url)
            if response.status_code == 404:
                return None
            if response.status_code != 200:
                logger.debug(
                    "API Nacional NFS-e retornou %d para %s",
                    response.status_code,
                    path,
                )
                return None
            return response.json()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.debug("Falha na API Nacional NFS-e (%s): %s", path, exc)
            return None

    async def consultar_por_chave(self, chave_acesso: str) -> dict[str, Any] | None:
        """
        Consulta uma NFS-e pela chave de acesso.

        Endpoint: GET /nfse/{chaveAcesso}
        Retorna None se a nota não for encontrada, se houver erro de autenticação
        (certificado não configurado) ou qualquer falha de rede.
        """
        try:
            return await self._get(f"/nfse/{chave_acesso}")
        except Exception as exc:
            logger.debug("Erro inesperado em consultar_por_chave (%s): %s", chave_acesso, exc)
            return None
