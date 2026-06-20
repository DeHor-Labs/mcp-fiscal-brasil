"""Testes de normalizacao de entradas do wrapper MCP do simulador de reforma tributaria.

Cobre: variantes sem acento, maiusculas, abreviacoes e erros amigaveis para
setor e regime_atual passados pelo LLM sem acento ou em caixa diferente.
"""

from __future__ import annotations

import pytest

from mcp_fiscal_brasil.server import _normalizar_regime, _normalizar_setor

# ---------------------------------------------------------------------------
# Normalizacao de setor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        # Com acento (entradas canonicas)
        ("comércio", "comércio"),
        ("serviços", "serviços"),
        ("indústria", "indústria"),
        # Sem acento (caso tipico de LLM)
        ("comercio", "comércio"),
        ("servicos", "serviços"),
        ("industria", "indústria"),
        # Maiusculas
        ("COMERCIO", "comércio"),
        ("SERVICOS", "serviços"),
        ("INDUSTRIA", "indústria"),
        # Misto
        ("Comercio", "comércio"),
        ("Serviços", "serviços"),
        ("Industria", "indústria"),
        # Espacos extras
        ("  comercio  ", "comércio"),
    ],
)
def test_normalizar_setor_aceita_variantes(entrada: str, esperado: str) -> None:
    assert _normalizar_setor(entrada) == esperado


def test_normalizar_setor_invalido_levanta_erro_amigavel() -> None:
    with pytest.raises(ValueError, match=r"comércio.*serviços.*indústria"):
        _normalizar_setor("varejo")


def test_normalizar_setor_invalido_menciona_entrada() -> None:
    with pytest.raises(ValueError, match="desconhecido"):
        _normalizar_setor("desconhecido")


# ---------------------------------------------------------------------------
# Normalizacao de regime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        # Canonicos
        ("Simples Nacional", "Simples Nacional"),
        ("Lucro Presumido", "Lucro Presumido"),
        ("Lucro Real", "Lucro Real"),
        # Sem acento e minusculo
        ("simples nacional", "Simples Nacional"),
        ("lucro presumido", "Lucro Presumido"),
        ("lucro real", "Lucro Real"),
        # Maiusculas
        ("SIMPLES NACIONAL", "Simples Nacional"),
        ("LUCRO PRESUMIDO", "Lucro Presumido"),
        ("LUCRO REAL", "Lucro Real"),
        # Abreviacoes suportadas
        ("simples", "Simples Nacional"),
        ("presumido", "Lucro Presumido"),
        ("real", "Lucro Real"),
        # Espacos extras
        ("  simples nacional  ", "Simples Nacional"),
    ],
)
def test_normalizar_regime_aceita_variantes(entrada: str, esperado: str) -> None:
    assert _normalizar_regime(entrada) == esperado


def test_normalizar_regime_invalido_levanta_erro_amigavel() -> None:
    with pytest.raises(ValueError, match=r"Simples Nacional.*Lucro Presumido.*Lucro Real"):
        _normalizar_regime("mei")


def test_normalizar_regime_invalido_menciona_entrada() -> None:
    with pytest.raises(ValueError, match="desconhecido"):
        _normalizar_regime("desconhecido")
