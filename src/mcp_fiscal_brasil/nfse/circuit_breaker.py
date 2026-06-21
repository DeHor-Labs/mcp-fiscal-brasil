"""Circuit breaker para a API Nacional NFS-e (ADN).

Protege contra falhas de disponibilidade da ADN (5xx, timeout, erro de rede),
que sao representadas por NFSeNacionalUnavailableError. Respostas de negocio
como 404 (nota nao encontrada) nao contam como falha de disponibilidade.

Estados:
- CLOSED: circuito fechado, chamadas passam normalmente.
- OPEN: circuito aberto, chamadas sao curto-circuitadas sem tocar a rede.
- HALF_OPEN: cooldown expirou, permite 1 tentativa de teste.
  - Sucesso -> CLOSED (zera contadores).
  - Falha -> OPEN (cooldown reinicia).
"""

from __future__ import annotations

import time
from collections import deque
from enum import Enum

__all__ = ["CircuitBreaker", "CircuitState"]

# Parametros padrao conservadores para a ADN (servico governamental)
_DEFAULT_FAILURE_THRESHOLD = 5  # falhas consecutivas para abrir
_DEFAULT_WINDOW_SECONDS = 60  # janela de observacao (segundos)
_DEFAULT_COOLDOWN_SECONDS = 120  # tempo de espera antes do half-open (segundos)


class CircuitState(Enum):
    """Estados possiveis do circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker de tres estados para servicos externos com falhas transientes.

    Uso tipico:
        cb = CircuitBreaker()
        if cb.is_open:
            raise NFSeNacionalUnavailableError("circuito aberto")
        try:
            resultado = await _chamar_api()
            cb.record_success()
        except NFSeNacionalUnavailableError:
            cb.record_failure()
            raise
    """

    def __init__(
        self,
        failure_threshold: int = _DEFAULT_FAILURE_THRESHOLD,
        window_seconds: float = _DEFAULT_WINDOW_SECONDS,
        cooldown_seconds: float = _DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        # Timestamps (monotonic) das falhas recentes dentro da janela.
        # maxlen=failure_threshold limita a memória: nunca armazenamos mais entradas
        # do que o limiar exige para abrir o circuito. A poda por janela de tempo
        # continua correta porque _evict_old_failures remove as entradas mais antigas
        # antes de qualquer comparação com o limiar.
        self._failure_times: deque[float] = deque(maxlen=failure_threshold)
        # Momento em que o circuito pode tentar a transicao para HALF_OPEN
        self._open_until: float | None = None

    # ------------------------------------------------------------------
    # Propriedades de estado
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Estado atual do circuito (CLOSED, OPEN ou HALF_OPEN)."""
        if self._open_until is None:
            return CircuitState.CLOSED
        if time.monotonic() < self._open_until:
            return CircuitState.OPEN
        return CircuitState.HALF_OPEN

    @property
    def is_open(self) -> bool:
        """True somente quando o circuito esta OPEN (nao inclui HALF_OPEN)."""
        return self.state == CircuitState.OPEN

    @property
    def failure_count(self) -> int:
        """Quantidade de falhas dentro da janela de observacao atual."""
        self._evict_old_failures()
        return len(self._failure_times)

    # ------------------------------------------------------------------
    # Registro de eventos
    # ------------------------------------------------------------------

    def record_failure(self) -> None:
        """Registra uma falha de disponibilidade e abre o circuito se necessario.

        Em HALF_OPEN: qualquer falha reabre o circuito imediatamente.
        Em OPEN: sem efeito (circuito ja esta aberto).
        Em CLOSED: incrementa contador; abre o circuito ao atingir o limiar.
        """
        current_state = self.state
        if current_state == CircuitState.OPEN:
            return

        now = time.monotonic()

        if current_state == CircuitState.HALF_OPEN:
            # Falha em tentativa de teste -> reabre com novo cooldown
            self._failure_times.clear()
            self._failure_times.append(now)
            self._open_until = now + self.cooldown_seconds
            return

        # CLOSED: adiciona falha e verifica se atingiu o limiar
        self._failure_times.append(now)
        self._evict_old_failures()

        if len(self._failure_times) >= self.failure_threshold:
            self._open_until = now + self.cooldown_seconds

    def record_success(self) -> None:
        """Registra uma requisicao bem-sucedida.

        Em HALF_OPEN: fecha o circuito e zera todos os contadores.
        Em CLOSED/OPEN: sem efeito significativo (nao altera estado).
        """
        if self.state == CircuitState.HALF_OPEN:
            self._failure_times.clear()
            self._open_until = None

    # ------------------------------------------------------------------
    # Utilitarios internos
    # ------------------------------------------------------------------

    def _evict_old_failures(self) -> None:
        """Remove registros de falhas mais antigos que a janela de observacao."""
        cutoff = time.monotonic() - self.window_seconds
        while self._failure_times and self._failure_times[0] < cutoff:
            self._failure_times.popleft()
