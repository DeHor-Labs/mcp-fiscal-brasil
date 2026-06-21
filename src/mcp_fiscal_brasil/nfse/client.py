"""
Cliente para a API Nacional NFS-e (Sistema Nacional NFS-e - adn.nfse.gov.br).

IMPORTANTE: A API Nacional exige certificado digital ICP-Brasil com mTLS.
Sem certificado configurado, todas as chamadas retornam None (nota nao encontrada)
ou levantam NFSeNacionalUnavailableError (5xx, timeout, falha de rede).

Referência: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao
"""

import logging
import time
from typing import Any
from urllib.parse import quote

import httpx

from mcp_fiscal_brasil.nfse.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# URL base da API de Dados Nacionais (ADN) em produção
_BASE_URL = "https://adn.nfse.gov.br"
# Timeout conservador: a API pode ser lenta
_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)

# Singleton do circuit breaker compartilhado entre todas as chamadas a consultar_nfse().
#
# O NFSeNacionalClient é instanciado a cada requisição MCP (lifecycle simples, sem recurso
# a fechar). O CircuitBreaker, por outro lado, é estado puro (sem recurso externo) e
# precisa persistir entre chamadas para que o limiar de falhas acumule corretamente.
#
# Asyncio é single-threaded: não há race em record_failure/record_success porque
# nenhum dos dois contém um ponto de suspensão (await), portanto não há interleaving
# entre corrotinas ao manipular _failure_times/_open_until.
_circuit_breaker: CircuitBreaker = CircuitBreaker()


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

    Circuit breaker integrado:
    - Abre após 5 falhas de disponibilidade em janela de 60s.
    - Cooldown de 120s antes do half-open (1 tentativa de teste).
    - Respostas 404 nao contam como falha de disponibilidade.
    """

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")
        # Referência ao singleton de módulo: estado persiste entre chamadas MCP.
        self.circuit_breaker = _circuit_breaker

    async def _get(self, path: str) -> dict[str, Any] | None:
        """
        Executa GET na API Nacional com circuit breaker.

        Retorna None para 404 (nota não encontrada).
        Levanta NFSeNacionalUnavailableError para 5xx, timeout e falha de rede,
        e tambem quando o circuito esta aberto (curto-circuito sem tocar a rede).
        """
        if self.circuit_breaker.is_open:
            restante = max(0.0, (self.circuit_breaker._open_until or 0.0) - time.monotonic())
            raise NFSeNacionalUnavailableError(
                f"circuit breaker aberto para a ADN (reaberto em ~{restante:.0f}s)"
            )

        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url)
            if response.status_code == 404:
                # Nota nao encontrada: nao e falha de disponibilidade
                return None
            if response.status_code != 200:
                exc = NFSeNacionalUnavailableError(f"status={response.status_code} path={path}")
                self.circuit_breaker.record_failure()
                raise exc
            self.circuit_breaker.record_success()
            return response.json()  # type: ignore[no-any-return]
        except NFSeNacionalUnavailableError:
            raise
        except httpx.HTTPError as exc:
            self.circuit_breaker.record_failure()
            raise NFSeNacionalUnavailableError(f"path={path}") from exc

    async def consultar_por_chave(self, chave_acesso: str) -> dict[str, Any] | None:
        """
        Consulta uma NFS-e pela chave de acesso.

        Endpoint: GET /nfse/{chaveAcesso}

        A chave é codificada com urllib.parse.quote para evitar injecao de
        caracteres de controle de rota (/, ?, #) no segmento de URL.

        Retorna None se a nota não for encontrada (HTTP 404).
        Levanta NFSeNacionalUnavailableError se a API estiver indisponível
        ou se o circuit breaker estiver aberto.
        """
        chave_segmento = quote(chave_acesso, safe="")
        return await self._get(f"/nfse/{chave_segmento}")
