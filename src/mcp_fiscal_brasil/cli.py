"""CLI standalone do mcp-fiscal-brasil.

Permite usar as ferramentas fiscais direto no terminal sem precisar
de servidor MCP. Util para automacao em scripts shell e exploracao rapida.

Exemplos:
    mcp-fiscal-brasil cnpj 12345678000190
    mcp-fiscal-brasil cnpj 12345678000190 --json
    mcp-fiscal-brasil compliance 12345678000190
    mcp-fiscal-brasil regimes --faturamento 500000 --setor servicos --folha 180000
    mcp-fiscal-brasil cpf 12345678909
    mcp-fiscal-brasil cep 01001000
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import typer
from pydantic import BaseModel

from . import __version__
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


@app.command()
def version() -> None:
    """Exibe versao do pacote."""
    typer.echo(f"mcp-fiscal-brasil {__version__}")


@app.command()
def cnpj(
    numero: str = typer.Argument(..., help="CNPJ com ou sem formatacao"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Consulta dados cadastrais de um CNPJ."""
    resultado = asyncio.run(consultar_cnpj(numero))
    _print(resultado, as_json)


@app.command()
def cpf(
    numero: str = typer.Argument(..., help="CPF com ou sem formatacao"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Valida CPF brasileiro (digito verificador, offline)."""
    resultado = asyncio.run(validar_cpf_tool(numero))
    _print(resultado, as_json)


@app.command()
def cep(
    numero: str = typer.Argument(..., help="CEP com ou sem hifen"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Consulta endereco pelo CEP."""

    async def run() -> Any:
        client = CEPClient()
        return await client.get_address(numero)

    resultado = asyncio.run(run())
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

    resultado = asyncio.run(run())
    _print(resultado, as_json)


@app.command()
def municipio(
    codigo_ibge: str = typer.Argument(..., help="Codigo IBGE do municipio"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Consulta dados de um municipio pelo codigo IBGE."""

    async def run() -> Any:
        client = IBGEClient()
        return await client.get_municipality(int(codigo_ibge))

    resultado = asyncio.run(run())
    _print(resultado, as_json)


@app.command()
def compliance(
    cnpj: str = typer.Argument(..., help="CNPJ alvo da analise"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Analise consolidada de compliance fiscal (multiplas fontes)."""
    resultado = asyncio.run(analyze_cnpj_compliance(cnpj))
    _print(resultado, as_json)


@app.command()
def supplier(
    cnpj: str = typer.Argument(..., help="CNPJ do fornecedor"),
    estrito: bool = typer.Option(False, "--estrito", help="Criterios estritos"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Score de risco para due diligence de fornecedor."""
    resultado = asyncio.run(risk_score_supplier(cnpj, criterios_estritos=estrito))
    _print(resultado, as_json)


@app.command()
def regimes(
    faturamento: float = typer.Option(..., "--faturamento", help="Faturamento anual em reais"),
    setor: str = typer.Option(..., "--setor", help="comercio, servicos ou industria"),
    folha: float | None = typer.Option(None, "--folha", help="Folha anual (impacta Fator R)"),
    as_json: bool = typer.Option(False, "--json", help="Saida em JSON puro"),
) -> None:
    """Compara regimes tributarios (MEI/Simples/Lucro Presumido/Lucro Real)."""
    if setor not in ("comercio", "servicos", "industria"):
        typer.echo("Erro: setor deve ser comercio, servicos ou industria", err=True)
        raise typer.Exit(code=1)
    resultado = compare_tax_regimes(
        faturamento_anual=faturamento,
        setor=setor,  # type: ignore[arg-type]
        folha_pagamento_anual=folha,
    )
    _print(resultado, as_json)


def main() -> None:
    """Entry point do CLI."""
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\nInterrompido pelo usuario", err=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
