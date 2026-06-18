"""Demonstra consulta de CNPJ com retry simples, cache em memoria e fallback mock."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TypedDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from mcp_fiscal_brasil import FiscalBrasil, format_cnpj, validate_cnpj  # noqa: E402
from mcp_fiscal_brasil.cnpj.schemas import CNPJResponse  # noqa: E402


class CompanySummary(TypedDict):
    cnpj: str
    razao_social: str
    situacao_cadastral: str
    municipio: str | None
    uf: str | None
    origem: str


CNPJ_CACHE: dict[str, CompanySummary] = {}
MOCK_COMPANY: CompanySummary = {
    "cnpj": "33.000.167/0001-01",
    "razao_social": "PETROLEO BRASILEIRO S A PETROBRAS",
    "situacao_cadastral": "ATIVA",
    "municipio": "RIO DE JANEIRO",
    "uf": "RJ",
    "origem": "mock",
}


def normalize_cnpj(cnpj: str) -> str:
    return "".join(char for char in cnpj if char.isdigit())


def summarize_company(company: CNPJResponse) -> CompanySummary:
    return {
        "cnpj": format_cnpj(company.cnpj),
        "razao_social": company.razao_social,
        "situacao_cadastral": company.situacao_cadastral,
        "municipio": company.endereco.municipio if company.endereco else None,
        "uf": company.endereco.uf if company.endereco else None,
        "origem": company.origem,
    }


async def lookup_cnpj(cnpj: str, attempts: int = 2) -> CompanySummary:
    normalized = normalize_cnpj(cnpj)
    if normalized in CNPJ_CACHE:
        cached = CNPJ_CACHE[normalized].copy()
        cached["origem"] = f"{cached['origem']} cache"
        return cached

    if not validate_cnpj(cnpj):
        raise ValueError(f"CNPJ invalido: {cnpj}")

    async with FiscalBrasil() as fiscal:
        for attempt in range(1, attempts + 1):
            try:
                company = await fiscal.consultar_cnpj(cnpj)
                summary = summarize_company(company)
                CNPJ_CACHE[normalized] = summary
                return summary
            except Exception as exc:
                print(f"Tentativa {attempt}/{attempts} falhou: {exc}")
                if attempt < attempts:
                    await asyncio.sleep(0.5 * attempt)

    fallback = MOCK_COMPANY.copy()
    CNPJ_CACHE[normalized] = fallback
    return fallback


def print_company(company: CompanySummary) -> None:
    print(f"CNPJ: {company['cnpj']}")
    print(f"Razao social: {company['razao_social']}")
    print(f"Situacao: {company['situacao_cadastral']}")
    print(f"Municipio/UF: {company['municipio'] or '-'} / {company['uf'] or '-'}")
    print(f"Origem: {company['origem']}")


async def main() -> None:
    cnpj = "33.000.167/0001-01"

    print("=== Primeira consulta ===")
    print_company(await lookup_cnpj(cnpj))

    print("\n=== Segunda consulta, cache local ===")
    print_company(await lookup_cnpj(cnpj))


if __name__ == "__main__":
    asyncio.run(main())
