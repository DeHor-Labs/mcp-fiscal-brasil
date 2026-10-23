"""CLI standalone do mcp-fiscal-brasil.

Permite usar as ferramentas fiscais direto no terminal sem precisar
de servidor MCP. Util para automação em scripts shell e exploracao rápida.

Exemplos:
    mcp-fiscal-brasil cnpj 12345678000190
    mcp-fiscal-brasil cnpj 12345678000190 --json
    mcp-fiscal-brasil compliance 12345678000190
    mcp-fiscal-brasil regimes --faturamento 500000 --setor serviços --folha 180000
    mcp-fiscal-brasil cpf 12345678909
    mcp-fiscal-brasil cep 01001000

Toda saída é JSON estruturado (mesmo em erro): {"ok": true, ...} ou
{"ok": false, "erro": "...", "tipo": "...", "cnpj": ...}. Nenhum comando
vaza traceback: erro de negócio (FiscalError) sai com código 1, erro
inesperado sai com código 2.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Coroutine
from typing import Any, NoReturn

import typer
from pydantic import BaseModel

from . import __version__
from ._core.errors import FiscalError
from .agentic import (
    analyze_cnpj_compliance,
    compare_tax_regimes,
    risk_score_supplier,
)
from .cep.client import CEPClient
from .cnpj.tools import consultar_cnpj
from .cpf.tools import validar_cpf_tool
from .ibge.client import IBGEClient
from .simples.client import SimplesClient

app = typer.Typer(
    name="mcp-fiscal-brasil",
    help="CLI fiscal brasileiro: CNPJ, CPF, Simples, NFe, SPED e mais.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _print(payload: BaseModel | dict[str, Any] | list[Any], as_json: bool) -> None:
    data: Any
    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json", exclude_none=True)
    else:
        data = payload
    if as_json:
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        _pretty(data, indent=0)


def _pretty(value: Any, indent: int) -> None:
    prefix = "  " * indent
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                typer.echo(f"{prefix}{k}:")
                _pretty(v, indent + 1)
            else:
                typer.echo(f"{prefix}{k}: {v}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                _pretty(item, indent)
                typer.echo("")
            else:
                typer.echo(f"{prefix}- {item}")
    else:
        typer.echo(f"{prefix}{value}")


def _fail(exc: Exception, cnpj: str | None, code: int) -> NoReturn:
    """Imprime um erro como JSON estruturado no stdout e sai sem traceback."""
    payload = {
        "ok": False,
        "erro": str(exc),
        "tipo": type(exc).__name__,
        "cnpj": cnpj,
    }
    typer.echo(json.dumps(payload, ensure_ascii=False))
    raise typer.Exit(code=code)


def _run(coro: Coroutine[Any, Any, Any], *, cnpj: str | None = None) -> Any:
    """Executa uma coroutine do CLI convertendo erros em JSON (nunca traceback)."""
    try:
        return asyncio.run(coro)
    except FiscalError as exc:
        _fail(exc, cnpj, code=1)
    except Exception as exc:  # CLI nunca deve vazar traceback
        _fail(exc, cnpj, code=2)


def _call(func: Any, cnpj: str | None = None) -> Any:
    """Executa uma função síncrona do CLI convertendo erros em JSON (nunca traceback)."""
    try:
        return func()
    except FiscalError as exc:
        _fail(exc, cnpj, code=1)
    except Exception as exc:  # CLI nunca deve vazar traceback
        _fail(exc, cnpj, code=2)


@app.command()
def version() -> None:
    """Exibe versão do pacote."""
    typer.echo(f"mcp-fiscal-brasil {__version__}")


@app.command()
def cnpj(
    número: str = typer.Argument(..., help="CNPJ com ou sem formatacao"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Consulta dados cadastrais de um CNPJ."""
    resultado = _run(consultar_cnpj(número), cnpj=número)
    _print(resultado, as_json)


@app.command()
def cpf(
    número: str = typer.Argument(..., help="CPF com ou sem formatacao"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Valida CPF brasileiro (digito verificador, offline)."""
    resultado = _run(validar_cpf_tool(número))
    _print(resultado, as_json)


@app.command()
def cep(
    número: str = typer.Argument(..., help="CEP com ou sem hifen"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Consulta endereco pelo CEP."""

    async def run() -> Any:
        client = CEPClient()
        return await client.get_address(número)

    resultado = _run(run())
    _print(resultado, as_json)


@app.command()
def simples(
    cnpj: str = typer.Argument(..., help="CNPJ com ou sem formatacao"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Consulta situacao no Simples Nacional."""

    async def run() -> Any:
        client = SimplesClient()
        return await client.get_simples_status(cnpj)

    resultado = _run(run(), cnpj=cnpj)
    _print(resultado, as_json)


@app.command()
def municipio(
    codigo_ibge: str = typer.Argument(..., help="Codigo IBGE do municipio"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Consulta dados de um municipio pelo código IBGE."""

    async def run() -> Any:
        client = IBGEClient()
        return await client.get_municipality(int(codigo_ibge))

    resultado = _run(run())
    _print(resultado, as_json)


@app.command()
def compliance(
    cnpj: str = typer.Argument(..., help="CNPJ alvo da analise"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Analise consolidada de compliance fiscal (multiplas fontes)."""
    resultado = _run(analyze_cnpj_compliance(cnpj), cnpj=cnpj)
    _print(resultado, as_json)


@app.command()
def supplier(
    cnpj: str = typer.Argument(..., help="CNPJ do fornecedor"),
    estrito: bool = typer.Option(False, "--estrito", help="Criterios estritos"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Score de risco para due diligence de fornecedor."""
    resultado = _run(
        risk_score_supplier(cnpj, criterios_estritos=estrito),
        cnpj=cnpj,
    )
    _print(resultado, as_json)


@app.command()
def regimes(
    faturamento: float = typer.Option(..., "--faturamento", help="Faturamento anual em reais"),
    setor: str = typer.Option(..., "--setor", help="comércio, serviços ou indústria"),
    folha: float | None = typer.Option(None, "--folha", help="Folha anual (impacta Fator R)"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Compara regimes tributarios (MEI/Simples/Lucro Presumido/Lucro Real)."""
    if setor not in ("comércio", "serviços", "indústria"):
        _fail(
            ValueError("setor deve ser comércio, serviços ou indústria"),
            cnpj=None,
            code=1,
        )
    resultado = _call(
        lambda: compare_tax_regimes(
            faturamento_anual=faturamento,
            setor=setor,  # type: ignore[arg-type]
            folha_pagamento_anual=folha,
        )
    )
    _print(resultado, as_json)


def main() -> None:
    """Entry point do CLI."""
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\nInterrompido pelo usuário", err=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
