"""Testes para o circuit breaker da API Nacional NFS-e (ADN).

Comportamento esperado:
- Abre após 5 falhas de DISPONIBILIDADE (5xx, timeout, erro de rede) em janela de 60s.
- Enquanto ABERTO: curto-circuita sem bater na rede, levanta NFSeNacionalUnavailableError.
- Half-open após cooldown de 120s: permite 1 tentativa de teste.
  - Se a tentativa falha -> volta a ABERTO.
  - Se a tentativa tem sucesso -> fecha o circuito e zera o contador.
- Respostas 404 (nota não encontrada) NÃO contam como falha de disponibilidade.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

import mcp_fiscal_brasil.nfse.client as _client_module
from mcp_fiscal_brasil.nfse.circuit_breaker import CircuitBreaker, CircuitState
from mcp_fiscal_brasil.nfse.client import NFSeNacionalClient, NFSeNacionalUnavailableError

# ---------------------------------------------------------------------------
# Testes unitários do CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreakerEstadoInicial:
    """Valida o estado inicial e os parâmetros padrão do circuit breaker."""

    def test_estado_inicial_e_fechado(self) -> None:
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_parametros_padrao(self) -> None:
        cb = CircuitBreaker()
        assert cb.failure_threshold == 5
        assert cb.window_seconds == 60
        assert cb.cooldown_seconds == 120

    def test_parametros_customizaveis(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, window_seconds=30, cooldown_seconds=60)
        assert cb.failure_threshold == 3
        assert cb.window_seconds == 30
        assert cb.cooldown_seconds == 60

    def test_is_open_retorna_false_quando_fechado(self) -> None:
        cb = CircuitBreaker()
        assert cb.is_open is False

    def test_contador_inicial_e_zero(self) -> None:
        cb = CircuitBreaker()
        assert cb.failure_count == 0


class TestCircuitBreakerAbertura:
    """Valida abertura do circuito após limiar de falhas."""

    def test_registrar_falha_incrementa_contador(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60)
        cb.record_failure()
        assert cb.failure_count == 1

    def test_circuito_abre_apos_limiar_de_falhas(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_circuito_nao_abre_antes_do_limiar(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_is_open_retorna_true_quando_aberto(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60)
        for _ in range(5):
            cb.record_failure()
        assert cb.is_open is True

    def test_falhas_fora_da_janela_nao_abrem_circuito(self) -> None:
        """Falhas mais antigas que window_seconds nao devem ser contadas."""
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60)
        # Simula 4 falhas no passado (fora da janela)
        past = time.monotonic() - 70  # 70s atrás > window_seconds=60
        for _ in range(4):
            cb._failure_times.append(past)  # type: ignore[attr-defined]
        # 1 falha recente: total na janela = 1, nao deve abrir
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1


class TestCircuitBreakerCooldown:
    """Valida transição OPEN -> HALF_OPEN após cooldown."""

    def test_circuito_fica_em_half_open_apos_cooldown(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60, cooldown_seconds=120)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Simula passagem do cooldown
        cb._open_until = time.monotonic() - 1  # type: ignore[attr-defined]
        assert cb.state == CircuitState.HALF_OPEN

    def test_is_open_retorna_false_quando_half_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60, cooldown_seconds=120)
        for _ in range(5):
            cb.record_failure()
        cb._open_until = time.monotonic() - 1  # type: ignore[attr-defined]
        assert cb.is_open is False

    def test_falha_em_half_open_volta_para_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60, cooldown_seconds=120)
        for _ in range(5):
            cb.record_failure()
        cb._open_until = time.monotonic() - 1  # type: ignore[attr-defined]
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_sucesso_em_half_open_fecha_circuito(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60, cooldown_seconds=120)
        for _ in range(5):
            cb.record_failure()
        cb._open_until = time.monotonic() - 1  # type: ignore[attr-defined]
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_sucesso_em_half_open_zera_contadores(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60, cooldown_seconds=120)
        for _ in range(5):
            cb.record_failure()
        cb._open_until = time.monotonic() - 1  # type: ignore[attr-defined]
        cb.record_success()
        # Após fechar, deve ser possivel acumular falhas de novo ate o limiar
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerSucesso:
    """Valida comportamento do record_success quando circuito está fechado."""

    def test_sucesso_quando_fechado_nao_muda_estado(self) -> None:
        cb = CircuitBreaker()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_sucesso_quando_fechado_nao_zera_falhas_recentes(self) -> None:
        """Sucessos nao apagam falhas recentes quando circuito está fechado."""
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 2


# ---------------------------------------------------------------------------
# Testes de integração: circuit breaker no NFSeNacionalClient
# ---------------------------------------------------------------------------


class TestNFSeClienteComCircuitBreaker:
    """Valida que o NFSeNacionalClient usa o circuit breaker corretamente.

    Cada teste recebe um CircuitBreaker isolado via patch no singleton de módulo,
    garantindo que o estado de um teste não vaze para os demais.
    """

    @pytest.fixture(autouse=True)
    def _cb_isolado(self) -> None:  # type: ignore[return]
        """Substitui o singleton _circuit_breaker por uma instância limpa por teste."""
        from mcp_fiscal_brasil.nfse.circuit_breaker import CircuitBreaker

        with patch.object(_client_module, "_circuit_breaker", CircuitBreaker()):
            yield

    @pytest.mark.asyncio
    async def test_cinco_erros_5xx_abrem_o_circuito(self) -> None:
        """Após 5 respostas 5xx consecutivas, o circuito deve abrir."""
        client = NFSeNacionalClient()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.get.return_value.status_code = 503

            for _ in range(5):
                with pytest.raises(NFSeNacionalUnavailableError):
                    await client._get("/nfse/CHAVE")

        assert client.circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuito_aberto_curto_circuita_sem_rede(self) -> None:
        """Com circuito aberto, _get deve falhar sem fazer chamada HTTP."""
        client = NFSeNacionalClient()
        # Abre o circuito manualmente
        for _ in range(5):
            client.circuit_breaker.record_failure()

        with patch("httpx.AsyncClient") as mock_cls:
            with pytest.raises(NFSeNacionalUnavailableError):
                await client._get("/nfse/CHAVE")
            # Nenhuma chamada HTTP deve ter ocorrido
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_erros_404_nao_contam_como_falha_de_disponibilidade(self) -> None:
        """HTTP 404 (nota nao encontrada) nao deve incrementar o contador de falhas."""
        client = NFSeNacionalClient()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.get.return_value.status_code = 404

            for _ in range(10):
                resultado = await client._get("/nfse/INEXISTENTE")
                assert resultado is None

        # Apenas 404s -> circuito deve continuar fechado
        assert client.circuit_breaker.state == CircuitState.CLOSED
        assert client.circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_timeout_conta_como_falha_de_disponibilidade(self) -> None:
        """Timeout de rede deve incrementar o contador de falhas."""
        import httpx

        client = NFSeNacionalClient()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.get.side_effect = httpx.TimeoutException("timeout", request=None)

            for _i in range(4):
                with pytest.raises(NFSeNacionalUnavailableError):
                    await client._get("/nfse/CHAVE")

        assert client.circuit_breaker.failure_count == 4
        assert client.circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_sucesso_apos_half_open_fecha_circuito(self) -> None:
        """Requisição bem-sucedida em HALF_OPEN fecha o circuito."""
        client = NFSeNacionalClient()
        # Força abertura
        for _ in range(5):
            client.circuit_breaker.record_failure()
        # Força transição para HALF_OPEN
        client.circuit_breaker._open_until = time.monotonic() - 1  # type: ignore[attr-defined]
        assert client.circuit_breaker.state == CircuitState.HALF_OPEN

        dados_mock = {"numero": "123", "municipio": "SP"}
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = lambda: dados_mock
            mock_http.get.return_value = mock_response

            resultado = await client._get("/nfse/CHAVE")

        assert resultado == dados_mock
        assert client.circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_falha_em_half_open_reabre_circuito(self) -> None:
        """Falha 5xx em HALF_OPEN deve reabrir o circuito."""
        client = NFSeNacionalClient()
        for _ in range(5):
            client.circuit_breaker.record_failure()
        client.circuit_breaker._open_until = time.monotonic() - 1  # type: ignore[attr-defined]
        assert client.circuit_breaker.state == CircuitState.HALF_OPEN

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_http.get.return_value.status_code = 500

            with pytest.raises(NFSeNacionalUnavailableError):
                await client._get("/nfse/CHAVE")

        assert client.circuit_breaker.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Teste de regressão: prova o bug HIGH (estado zerava a cada chamada MCP)
# ---------------------------------------------------------------------------


class TestCircuitBreakerPersistenciaSingleton:
    """
    Prova que o circuit breaker persiste estado entre instâncias de NFSeNacionalClient.

    Este teste exercita o caminho real: consultar_nfse() em tools.py instancia
    NFSeNacionalClient() a cada chamada. Antes do fix, o estado do circuit breaker
    zerava a cada instância e o circuito NUNCA abria em produção.

    Estrutura do teste:
    - Substitui o singleton _circuit_breaker por um isolado para não contaminar
      outros testes (o singleton real persiste entre testes no mesmo processo).
    - Mocka httpx na camada HTTP para controlar as respostas sem rede real.
    - Verifica que após 5 falhas via consultar_nfse(), a 6ª chamada curto-circuita
      sem tocar o httpx.AsyncClient (mock.assert_not_called() no AsyncClient).
    """

    @pytest.mark.asyncio
    async def test_circuito_abre_e_curto_circuita_via_tools(self) -> None:
        """
        Após 5 falhas 5xx acumuladas via consultar_nfse(), a 6ª chamada deve
        curto-circuitar sem tocar a rede.

        ANTES do fix: cada consultar_nfse() criava NFSeNacionalClient() com CircuitBreaker()
        novo -> estado zerava -> circuito nunca abria -> proteção ineficaz.

        DEPOIS do fix: todas as instâncias compartilham _circuit_breaker singleton
        -> estado acumula -> circuito abre -> 6ª chamada curto-circuita.
        """
        from mcp_fiscal_brasil.nfse.tools import consultar_nfse

        # Circuit breaker isolado para este teste (evita contaminação do singleton global)
        cb_isolado = CircuitBreaker(failure_threshold=5, window_seconds=60, cooldown_seconds=120)

        with patch.object(_client_module, "_circuit_breaker", cb_isolado):
            # Simula 5 chamadas com a ADN retornando 503
            with patch("httpx.AsyncClient") as mock_http_cls:
                mock_http = AsyncMock()
                mock_http_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_http.get.return_value.status_code = 503

                for _ in range(5):
                    # Cada chamada instancia NFSeNacionalClient() internamente em tools.py
                    resultado = await consultar_nfse(
                        numero="CHAVE-TESTE",
                        municipio="São Paulo",
                        uf="SP",
                    )
                    # Com 5xx, cai no fallback municipal (não levanta exceção para o chamador)
                    assert resultado["fonte"] == "fallback_portal_municipal"

            # Circuito deve estar OPEN após 5 falhas acumuladas
            assert cb_isolado.state == CircuitState.OPEN, (
                "Circuito deveria estar OPEN após 5 falhas, mas está "
                f"{cb_isolado.state}. Isso indica que o estado zerou entre chamadas "
                "(bug do singleton ausente)."
            )

            # 6ª chamada: httpx NÃO deve ser chamado (curto-circuito)
            with patch("httpx.AsyncClient") as mock_http_cls_6:
                resultado_6 = await consultar_nfse(
                    numero="CHAVE-TESTE",
                    municipio="São Paulo",
                    uf="SP",
                )
                # Curto-circuito cai no fallback com motivo de circuit breaker aberto
                assert resultado_6["fonte"] == "fallback_portal_municipal"
                assert resultado_6["api_nacional_motivo"] is not None
                assert "circuit breaker" in (resultado_6["api_nacional_motivo"] or "").lower()
                # httpx.AsyncClient NÃO deve ter sido instanciado na 6ª chamada
                mock_http_cls_6.assert_not_called()
