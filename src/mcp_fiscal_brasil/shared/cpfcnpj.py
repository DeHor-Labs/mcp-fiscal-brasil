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

import asyncio
import threading
import time
from collections import deque
from typing import Any

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
# Pacote padrao de CPF: 26 (CPF D Simplificado), o mais barato que traz situacao
# cadastral. O pacote efetivo vem de settings.cpfcnpj_cpf_packet.
PACOTE_CPF = 26

# Teto de requisicoes por segundo da cpfcnpj.com.br. Cada consulta abre um
# HTTPClient novo, entao o limitador precisa coordenar o teto por todo o processo,
# entre event loops distintos: os metodos sincronos do SDK (consultar_cpf_sync/
# consultar_cnpj_sync) chamam asyncio.run, abrindo um loop novo a cada chamada. Sem
# isso, chamadas sincronas sucessivas somariam orcamentos independentes e poderiam
# ultrapassar o teto, recebendo o erro 1007 (HTTP 429). A maioria dos pacotes
# (CPF/CNPJ/IE) segue 20 req/s. Os pacotes de NF-e/NFC-e por chave (100/102) tem teto
# proprio de 2 req/s por conta na documentacao do provedor; ultrapassar devolve
# HTTP 429 + erroCodigo 1007 (sem cobrar credito).
CPFCNPJ_MAX_REQUISICOES_POR_SEGUNDO = 20
CPFCNPJ_NFE_MAX_REQUISICOES_POR_SEGUNDO = 2

# Pacotes com teto reduzido de requisicoes por segundo.
PACOTES_LIMITE_REDUZIDO = frozenset({PACOTE_NFE, PACOTE_NFCE})


class _LimitadorDeProcesso:
    """Limitador de requisicoes por segundo compartilhado por todo o processo.

    Independe do event loop: nao guarda referencia a loop algum. Ao adquirir, calcula
    sob o lock o instante em que a proxima requisicao pode partir, reserva a vaga e
    dorme no loop corrente ate ela (asyncio.sleep). Assim varios ``asyncio.run``
    consecutivos (como os dos metodos sincronos do SDK) dividem o mesmo orcamento e
    nada acumula por loop. O agendamento e protegido por um ``threading.Lock``, entao
    tambem e seguro entre threads.

    Usa uma janela deslizante de ``janela`` segundos: ate ``taxa`` requisicoes cabem
    na janela sem espera; a seguinte so parte quando a mais antiga sai da janela.
    """

    def __init__(self, taxa: int, janela: float = 1.0) -> None:
        self.taxa = taxa
        self.janela = janela
        self._lock = threading.Lock()
        self._agendadas: deque[float] = deque()

    async def acquire(self, amount: float = 1) -> None:
        # A vaga so e registrada quando existe de fato: depois de dormir, a janela
        # e reavaliada sob o lock, porque outra tarefa (ou thread) pode ter ocupado
        # o espaco enquanto esta esperava. Assim nenhuma requisicao parte com a
        # janela cheia, mesmo se o sleep retomar atrasado.
        while True:
            with self._lock:
                agora = time.monotonic()
                limite = agora - self.janela
                while self._agendadas and self._agendadas[0] <= limite:
                    self._agendadas.popleft()
                if len(self._agendadas) < self.taxa:
                    self._agendadas.append(agora)
                    return
                espera = self._agendadas[0] + self.janela - agora
            await asyncio.sleep(max(0.0, espera))


def _rate_limit_para(pacote: int) -> int:
    """Teto de req/s do pacote: 2 para NF-e/NFC-e (100/102), 20 para os demais."""
    if pacote in PACOTES_LIMITE_REDUZIDO:
        return CPFCNPJ_NFE_MAX_REQUISICOES_POR_SEGUNDO
    return CPFCNPJ_MAX_REQUISICOES_POR_SEGUNDO


# Um limitador por grupo de req/s (20 padrao, 2 para NF-e/NFC-e), singleton de
# modulo compartilhado entre todos os event loops e threads do processo.
_limitadores_por_grupo: dict[int, _LimitadorDeProcesso] = {}
_limitadores_lock = threading.Lock()


def _get_limiter(pacote: int) -> _LimitadorDeProcesso:
    """Retorna o limitador de processo do grupo do pacote (singleton por grupo).

    Pacotes 100/102 compartilham um limitador de 2 req/s; os demais, um de 20 req/s.
    O mesmo objeto e devolvido em qualquer event loop ou thread, entao o teto vale
    por processo e nao acumula estado por loop.
    """
    grupo = _rate_limit_para(pacote)
    limitador = _limitadores_por_grupo.get(grupo)
    if limitador is None:
        with _limitadores_lock:
            limitador = _limitadores_por_grupo.get(grupo)
            if limitador is None:
                limitador = _LimitadorDeProcesso(grupo)
                _limitadores_por_grupo[grupo] = limitador
    return limitador


def provedor_configurado() -> bool:
    """Indica se o provedor premium cpfcnpj.com.br esta habilitado (token definido)."""
    return bool(settings.cpfcnpj_token.strip())


def _http_client(pacote: int) -> HTTPClient:
    return HTTPClient(
        settings.cpfcnpj_base_url,
        timeout=settings.cpfcnpj_timeout,
        max_retries=settings.mcp_fiscal_max_retries,
        cache_ttl=settings.mcp_fiscal_cache_ttl,
        rate_limit_per_second=_rate_limit_para(pacote),
        limiter=_get_limiter(pacote),
        # O token viaja no primeiro segmento do path: mascarar nos erros. Passar
        # o token como segredo literal cobre tambem bases com prefixo de path
        # (ex.: CPFCNPJ_BASE_URL=https://proxy/cpfcnpj), removendo-o de qualquer
        # url/mensagem/details mesmo fora do formato esperado.
        mask_first_path_segment=True,
        mask_secret=settings.cpfcnpj_token.strip() or None,
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
    async with _http_client(pacote) as client:
        data = await client.get(path)

    if data.get("status") != 1:
        codigo = data.get("erroCodigo")
        mensagem = data.get("erro") or "Consulta cpfcnpj.com.br sem sucesso."
        raise FiscalHTTPError(
            f"cpfcnpj.com.br retornou erro: {mensagem}",
            status_code=int(codigo) if isinstance(codigo, int) else 0,
            # Mascara o token (1o segmento) e tambem o documento (ultimo segmento):
            # a url viaja para access log/trace/proxy e nao pode expor o CPF/CNPJ/chave
            # consultado. A url real da requisicao (path acima) nao e alterada.
            url=f"{settings.cpfcnpj_base_url}/***/{pacote}/***",
            detail={"erro": mensagem, "erroCodigo": codigo},
        )

    return data


__all__ = [
    "PACOTE_CPF",
    "PACOTE_NFCE",
    "PACOTE_NFE",
    "consultar",
    "provedor_configurado",
]
