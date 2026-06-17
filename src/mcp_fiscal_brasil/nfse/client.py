"""
Cliente para a API Nacional NFS-e (Sistema Nacional NFS-e - adn.nfse.gov.br).

IMPORTANTE: A API Nacional exige certificado digital ICP-Brasil com mTLS.
Sem certificado configurado, todas as chamadas retornam None (nota nao encontrada)
ou levantam NFSeNacionalUnavailableError (5xx, timeout, falha de rede).

Referência: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# URL base da API de Dados Nacionais (ADN) em produção
_BASE_URL = "https://adn.nfse.gov.br"
# Timeout conservador: a API pode ser lenta
_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)


class NFSeNacionalUnavailableError(RuntimeError):
    """Levantada quando a API Nacional NFS-e está indisponível (5xx, timeout, rede).

    Distinto de retorno None (404 - nota não encontrada), esta exceção sinaliza
    que o serviço está temporariamente inacessível e o fallback deve ser acionado
    com motivo de indisponibilidade.
    """


class NFSeNacionalClient:
    """
    Cliente para consulta de NFS-e na API Nacional (adn.nfse.gov.br).

    Contratos:
    - Retorna None quando a nota não é encontrada (HTTP 404).
    - Levanta NFSeNacionalUnavailableError para 5xx, timeout e erros de rede.

    Isso permite que a camada superior distinga "nota não encontrada" de
    "API indisponível" ao montar o api_nacional_motivo no fallback.
    """

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    async def _get(self, path: str) -> dict[str, Any] | None:
        """
        Executa GET na API Nacional.

        Retorna None para 404 (nota não encontrada).
        Levanta NFSeNacionalUnavailableError para 5xx, timeout e falha de rede.
        """
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url)
            if response.status_code == 404:
                return None
            if response.status_code != 200:
                raise NFSeNacionalUnavailableError(f"status={response.status_code} path={path}")
            return response.json()  # type: ignore[no-any-return]
        except NFSeNacionalUnavailableError:
            raise
        except httpx.HTTPError as exc:
            raise NFSeNacionalUnavailableError(f"path={path}") from exc

    async def consultar_por_chave(self, chave_acesso: str) -> dict[str, Any] | None:
        """
        Consulta uma NFS-e pela chave de acesso.

        Endpoint: GET /nfse/{chaveAcesso}

        A chave é codificada com urllib.parse.quote para evitar injecao de
        caracteres de controle de rota (/, ?, #) no segmento de URL.

        Retorna None se a nota não for encontrada (HTTP 404).
        Levanta NFSeNacionalUnavailableError se a API estiver indisponível.
        """
        chave_segmento = quote(chave_acesso, safe="")
        return await self._get(f"/nfse/{chave_segmento}")
