"""Testes para shared/rate_limiter.py (SlidingWindowRateLimiter)."""

import asyncio
import time

import pytest

from mcp_fiscal_brasil.shared.exceptions import RateLimitError
from mcp_fiscal_brasil.shared.rate_limiter import (
    SlidingWindowRateLimiter,
    brasil_api_limiter,
    nfse_limiter,
    receita_limiter,
    sefaz_limiter,
)

# ---------------------------------------------------------------------------
# Inicializacao
# ---------------------------------------------------------------------------


def test_init_armazena_parametros():
    limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=5.0)
    assert limiter.max_requests == 10
    assert limiter.window_seconds == 5.0


def test_init_sem_timestamps():
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=1.0)
    # Antes de qualquer acquire, remaining deve retornar max_requests
    assert limiter.remaining("nova-chave") == 5


# ---------------------------------------------------------------------------
# acquire() - caminho feliz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_permite_ate_o_limite():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
    # As 3 primeiras aquisicoes devem passar sem erro
    await limiter.acquire("endpoint-a")
    await limiter.acquire("endpoint-a")
    await limiter.acquire("endpoint-a")


@pytest.mark.asyncio
async def test_acquire_chaves_independentes():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    # Cada chave tem seu proprio contador
    await limiter.acquire("chave-1")
    await limiter.acquire("chave-2")  # nao deve lancar, e outra chave


# ---------------------------------------------------------------------------
# acquire() - limite excedido
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_levanta_rate_limit_error_ao_exceder():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    await limiter.acquire("ep")
    await limiter.acquire("ep")

    with pytest.raises(RateLimitError) as exc_info:
        await limiter.acquire("ep")

    assert exc_info.value.endpoint == "ep"


@pytest.mark.asyncio
async def test_acquire_retry_after_e_positivo():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10.0)
    await limiter.acquire("ep")

    with pytest.raises(RateLimitError) as exc_info:
        await limiter.acquire("ep")

    assert exc_info.value.retry_after is not None
    assert exc_info.value.retry_after > 0
    assert exc_info.value.retry_after <= 10.0


@pytest.mark.asyncio
async def test_acquire_retry_after_decresce_com_tempo(monkeypatch):
    """retry_after deve ser menor quando a requisicao original e mais antiga."""
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10.0)

    # Injeta timestamp passado manualmente
    fake_time = [time.monotonic()]

    def fake_monotonic():
        return fake_time[0]

    import mcp_fiscal_brasil.shared.rate_limiter as rl_module

    monkeypatch.setattr(rl_module.time, "monotonic", fake_monotonic)

    await limiter.acquire("ep")
    # Avanca 5 segundos
    fake_time[0] += 5.0

    with pytest.raises(RateLimitError) as exc_info:
        await limiter.acquire("ep")

    # Faltam ~5 segundos, nao os 10 completos
    assert exc_info.value.retry_after is not None
    assert exc_info.value.retry_after <= 5.5  # margem de 0.5s


# ---------------------------------------------------------------------------
# Janela deslizante: requisicoes antigas saem da janela
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_janela_deslizante_permite_apos_expirar(monkeypatch):
    """Requisicoes fora da janela devem ser removidas permitindo novas."""
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=1.0)

    fake_time = [0.0]

    def fake_monotonic():
        return fake_time[0]

    import mcp_fiscal_brasil.shared.rate_limiter as rl_module

    monkeypatch.setattr(rl_module.time, "monotonic", fake_monotonic)

    # t=0: 2 requisicoes (preenche a janela)
    await limiter.acquire("ep")
    await limiter.acquire("ep")

    # t=0: deve falhar
    with pytest.raises(RateLimitError):
        await limiter.acquire("ep")

    # Avanca para alem da janela (1.1s > 1.0s)
    fake_time[0] = 1.1

    # Agora deve permitir 2 novas requisicoes
    await limiter.acquire("ep")
    await limiter.acquire("ep")


@pytest.mark.asyncio
async def test_janela_deslizante_parcial(monkeypatch):
    """Apenas parte das requisicoes sai da janela; limite ainda se aplica parcialmente."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=2.0)

    fake_time = [0.0]

    def fake_monotonic():
        return fake_time[0]

    import mcp_fiscal_brasil.shared.rate_limiter as rl_module

    monkeypatch.setattr(rl_module.time, "monotonic", fake_monotonic)

    # t=0: 2 requisicoes
    await limiter.acquire("ep")
    await limiter.acquire("ep")

    # t=1.5: 1 requisicao (ainda dentro da janela de 2s em relacao a t=0)
    fake_time[0] = 1.5
    await limiter.acquire("ep")  # 3ª - preenche

    # t=2.1: as 2 primeiras saem (t=0 < 2.1-2.0=0.1), mas a terceira (t=1.5) ainda esta
    fake_time[0] = 2.1
    await limiter.acquire("ep")  # deve passar (2 saíram, ficou 1, slot livre)


# ---------------------------------------------------------------------------
# remaining()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remaining_decresce_com_acquire():
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60.0)
    assert limiter.remaining("ep") == 5
    await limiter.acquire("ep")
    assert limiter.remaining("ep") == 4
    await limiter.acquire("ep")
    assert limiter.remaining("ep") == 3


@pytest.mark.asyncio
async def test_remaining_zero_quando_limite_atingido():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    await limiter.acquire("ep")
    await limiter.acquire("ep")
    assert limiter.remaining("ep") == 0


@pytest.mark.asyncio
async def test_remaining_nao_vai_abaixo_de_zero():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    await limiter.acquire("ep")
    # Mesmo que haja timestamps antigos que "sobram", nao vai negativo
    assert limiter.remaining("ep") >= 0


def test_remaining_chave_inexistente_retorna_max():
    limiter = SlidingWindowRateLimiter(max_requests=7, window_seconds=10.0)
    assert limiter.remaining("nunca-usada") == 7


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_limpa_historico_da_chave():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    await limiter.acquire("ep")
    await limiter.acquire("ep")
    assert limiter.remaining("ep") == 0

    limiter.reset("ep")
    assert limiter.remaining("ep") == 2


@pytest.mark.asyncio
async def test_reset_permite_novas_aquisicoes():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    await limiter.acquire("ep")

    with pytest.raises(RateLimitError):
        await limiter.acquire("ep")

    limiter.reset("ep")
    # Apos reset, deve funcionar novamente
    await limiter.acquire("ep")


def test_reset_chave_inexistente_nao_levanta():
    """reset() de chave que nunca foi usada nao deve levantar excecao."""
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=1.0)
    limiter.reset("chave-fantasma")  # nao deve lancar


@pytest.mark.asyncio
async def test_reset_nao_afeta_outras_chaves():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    await limiter.acquire("chave-a")
    await limiter.acquire("chave-b")

    limiter.reset("chave-a")
    assert limiter.remaining("chave-a") == 1
    assert limiter.remaining("chave-b") == 0


# ---------------------------------------------------------------------------
# Thread safety (asyncio.Lock)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_concorrente_respeita_limite():
    """Multiplas coroutines tentando acquire ao mesmo tempo nao devem ultrapassar o limite."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
    resultados = []

    async def tentar(i: int) -> None:
        try:
            await limiter.acquire("ep")
            resultados.append(("ok", i))
        except RateLimitError:
            resultados.append(("blocked", i))

    # Lanca 6 coroutines concorrentes
    await asyncio.gather(*[tentar(i) for i in range(6)])

    oks = [r for r in resultados if r[0] == "ok"]
    blocked = [r for r in resultados if r[0] == "blocked"]

    assert len(oks) == 3
    assert len(blocked) == 3


# ---------------------------------------------------------------------------
# Limiters pre-configurados
# ---------------------------------------------------------------------------


def test_limiters_pre_configurados_existem():
    assert receita_limiter.max_requests == 3
    assert receita_limiter.window_seconds == 60.0

    assert brasil_api_limiter.max_requests == 3
    assert brasil_api_limiter.window_seconds == 1.0

    assert sefaz_limiter.max_requests == 10
    assert sefaz_limiter.window_seconds == 60.0

    assert nfse_limiter.max_requests == 5
    assert nfse_limiter.window_seconds == 10.0
