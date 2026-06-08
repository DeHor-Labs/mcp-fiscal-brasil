"""API REST do mcp-fiscal-brasil via FastAPI.

Expoe as principais ferramentas fiscais como endpoints HTTP. Util para
integrar com sistemas que não falam MCP (frontends web, automação no-code,
microservicos legados).

Executar:
    mcp-fiscal-api
    # ou
    uvicorn mcp_fiscal_brasil.api:app --reload

OpenAPI docs em http://localhost:8000/docs (Swagger UI).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from ._core import get_logger
from ._core.config import settings
from .agentic import (
    analyze_cnpj_compliance,
    compare_tax_regimes,
    risk_score_supplier,
    summarize_sped,
    validate_nfe_full,
)
from .cep.client import CEPClient
from .cnpj.tools import consultar_cnpj
from .cpf.tools import validar_cpf_tool
from .ibge.client import IBGEClient
from .nfe.tools import validar_chave_nfe
from .shared.validators import validate_cnpj
from .simples.client import SimplesClient

logger = get_logger(__name__)

app = FastAPI(
    title="MCP Fiscal Brasil",
    version=__version__,
    description=(
        "API REST para integracoes fiscais brasileiras. Mesmas ferramentas do servidor "
        "MCP, expostas via HTTP. Util para frontends, no-code e legados."
    ),
)


def _only_digits(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def _validated_cnpj(cnpj: str) -> str:
    digits = _only_digits(cnpj)
    if len(digits) != 14 or not validate_cnpj(digits):
        raise HTTPException(status_code=400, detail="CNPJ inválido")
    return digits


def _allowed_file_base_dir() -> Path:
    try:
        base_dir = Path(settings.mcp_fiscal_file_base_dir).expanduser().resolve()
        base_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        base_dir.chmod(0o700)
    except OSError as exc:
        logger.error(
            "file_base_dir_unavailable",
            base_dir=settings.mcp_fiscal_file_base_dir,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Diretório base de arquivos indisponível: {exc}",
        ) from exc
    return base_dir


def _validated_input_file(path_value: str, *, label: str) -> Path:
    base_dir = _allowed_file_base_dir()
    file_path = Path(path_value).expanduser().resolve()

    try:
        file_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"{label} fora do diretório permitido",
        ) from exc

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"{label} não encontrado")
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"{label} não é um arquivo")
    return file_path


# ---------------------------------------------------------------------------
# Health + versão
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__
    service: str = "mcp-fiscal-brasil"


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Retorna status do serviço."""
    return HealthResponse()


# ---------------------------------------------------------------------------
# CNPJ
# ---------------------------------------------------------------------------


@app.get("/v1/cnpj/{cnpj}", tags=["cnpj"], summary="Consulta dados cadastrais")
async def cnpj_lookup(cnpj: str) -> dict[str, Any]:
    """Consulta dados cadastrais de uma empresa pelo CNPJ."""
    resultado = await consultar_cnpj(_validated_cnpj(cnpj))
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# CPF
# ---------------------------------------------------------------------------


@app.get("/v1/cpf/{cpf}", tags=["cpf"], summary="Valida CPF (digito verificador)")
async def cpf_validate(cpf: str) -> dict[str, Any]:
    """Valida CPF brasileiro (verificacao offline)."""
    resultado = await validar_cpf_tool(cpf)
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# CEP
# ---------------------------------------------------------------------------


@app.get("/v1/cep/{cep}", tags=["cep"], summary="Consulta endereco por CEP")
async def cep_lookup(cep: str) -> dict[str, Any]:
    """Consulta endereco pelo CEP."""
    client = CEPClient()
    resultado = await client.get_address(cep)
    data: dict[str, Any] = resultado.model_dump(mode="json", exclude_none=True)
    return data


# ---------------------------------------------------------------------------
# Simples Nacional
# ---------------------------------------------------------------------------


@app.get("/v1/simples/{cnpj}", tags=["simples"], summary="Situacao no Simples Nacional")
async def simples_lookup(cnpj: str) -> dict[str, Any]:
    """Consulta situacao da empresa no Simples Nacional."""
    client = SimplesClient()
    resultado = await client.get_simples_status(_validated_cnpj(cnpj))
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# IBGE
# ---------------------------------------------------------------------------


@app.get("/v1/ibge/municipio/{código}", tags=["ibge"], summary="Municipio por código IBGE")
async def ibge_municipio(código: int) -> dict[str, Any]:
    """Consulta dados de um municipio pelo código IBGE."""
    client = IBGEClient()
    resultado = await client.get_municipality(código)
    data: dict[str, Any] = resultado.model_dump(mode="json", exclude_none=True)
    return data


# ---------------------------------------------------------------------------
# NFe
# ---------------------------------------------------------------------------


@app.get("/v1/nfe/chave/{chave}", tags=["nfe"], summary="Valida chave de acesso de NFe")
async def nfe_chave_validate(chave: str) -> dict[str, Any]:
    """Valida formato e digito verificador da chave de NFe."""
    return await validar_chave_nfe(chave)


class NFeValidateRequest(BaseModel):
    xml_path: str = Field(description="Caminho absoluto para arquivo XML da NFe.")


@app.post("/v1/nfe/validate", tags=["nfe", "agentic"], summary="Validacao consolidada de NFe")
async def nfe_validate_full(req: NFeValidateRequest) -> dict[str, Any]:
    """Parse XML + válida chave + verifica situacao do emissor."""
    xml_path = _validated_input_file(req.xml_path, label="Arquivo XML")
    resultado = await validate_nfe_full(xml_path)
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# SPED
# ---------------------------------------------------------------------------


class SPEDSummarizeRequest(BaseModel):
    file_path: str = Field(description="Caminho absoluto para arquivo .txt do SPED.")


@app.post("/v1/sped/summarize", tags=["sped", "agentic"], summary="Sumario executivo de SPED")
async def sped_summarize(req: SPEDSummarizeRequest) -> dict[str, Any]:
    """Sumario executivo de arquivo SPED."""
    file_path = _validated_input_file(req.file_path, label="Arquivo SPED")
    resultado = await summarize_sped(file_path)
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# Agentic
# ---------------------------------------------------------------------------


@app.get(
    "/v1/agentic/compliance/{cnpj}",
    tags=["agentic"],
    summary="Analise consolidada de compliance",
)
async def agentic_compliance(cnpj: str) -> dict[str, Any]:
    """Compliance fiscal consolidado (CNPJ + Simples + MEI + CNAE)."""
    resultado = await analyze_cnpj_compliance(_validated_cnpj(cnpj))
    return resultado.model_dump(mode="json", exclude_none=True)


@app.get(
    "/v1/agentic/supplier/{cnpj}",
    tags=["agentic"],
    summary="Score de risco de fornecedor",
)
async def agentic_supplier(
    cnpj: str, estrito: bool = Query(False, description="Criterios estritos")
) -> dict[str, Any]:
    """Score de risco para due diligence de fornecedor."""
    resultado = await risk_score_supplier(_validated_cnpj(cnpj), criterios_estritos=estrito)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.get(
    "/v1/agentic/regimes",
    tags=["agentic"],
    summary="Comparativo de regimes tributarios",
)
def agentic_regimes(
    faturamento_anual: float = Query(..., gt=0),
    setor: Literal["comércio", "serviços", "indústria"] = Query(...),
    folha_pagamento_anual: float | None = Query(None, ge=0),
) -> dict[str, Any]:
    """Comparativo MEI/Simples/Lucro Presumido/Lucro Real."""
    resultado = compare_tax_regimes(
        faturamento_anual=faturamento_anual,
        setor=setor,
        folha_pagamento_anual=folha_pagamento_anual,
    )
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# Web UI demo
# ---------------------------------------------------------------------------


_DEMO_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>MCP Fiscal Brasil - Demo</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<style>
:root { --bg:#0f172a; --fg:#e2e8f0; --accent:#22d3ee; --card:#1e293b; --border:#334155; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family: system-ui, sans-serif; background:var(--bg); color:var(--fg);
       min-height:100vh; padding:2rem; line-height:1.6; }
.container { max-width:900px; margin:0 auto; }
h1 { font-size:2rem; margin-bottom:0.5rem; }
.tagline { color:#94a3b8; margin-bottom:2rem; }
.card { background:var(--card); border:1px solid var(--border); border-radius:8px;
        padding:1.5rem; margin-bottom:1.5rem; }
h2 { font-size:1.2rem; margin-bottom:1rem; color:var(--accent); }
.row { display:flex; gap:0.5rem; align-items:center; }
input { flex:1; background:#0f172a; border:1px solid var(--border); color:var(--fg);
        padding:0.6rem 0.8rem; border-radius:6px; font-size:1rem; font-family:inherit; }
button { background:var(--accent); color:#0f172a; border:0; padding:0.6rem 1.2rem;
         border-radius:6px; cursor:pointer; font-weight:600; font-size:1rem; }
button:hover { background:#67e8f9; }
pre { background:#0f172a; padding:1rem; border-radius:6px; overflow-x:auto;
      font-size:0.85rem; margin-top:1rem; max-height:400px; overflow-y:auto;
      border:1px solid var(--border); }
.footer { color:#64748b; margin-top:2rem; text-align:center; font-size:0.85rem; }
a { color:var(--accent); }
.htmx-indicator { display:none; color:var(--accent); margin-left:1rem; }
.htmx-request .htmx-indicator { display:inline; }
</style>
</head>
<body>
<div class="container">
  <h1>MCP Fiscal Brasil</h1>
  <p class="tagline">Demo interativa - dados fiscais brasileiros via API publica</p>

  <div class="card">
    <h2>Consulta de CNPJ</h2>
    <form hx-get="/v1/cnpj/" hx-target="#cnpj-result" hx-trigger="submit"
          hx-include="this" hx-on:submit="event.preventDefault();
          const v=this.querySelector('input').value.replace(/\\D/g,'');
          if(v.length===14){htmx.ajax('GET','/v1/cnpj/'+v,{target:'#cnpj-result',swap:'innerHTML'});}">
      <div class="row">
        <input type="text" placeholder="12.345.678/0001-90" required>
        <button type="submit">Consultar</button>
        <span class="htmx-indicator">Buscando...</span>
      </div>
    </form>
    <pre id="cnpj-result"></pre>
  </div>

  <div class="card">
    <h2>Compliance consolidado</h2>
    <form hx-on:submit="event.preventDefault();
          const v=this.querySelector('input').value.replace(/\\D/g,'');
          if(v.length===14){htmx.ajax('GET','/v1/agentic/compliance/'+v,
          {target:'#compl-result',swap:'innerHTML'});}">
      <div class="row">
        <input type="text" placeholder="CNPJ para analise completa" required>
        <button type="submit">Analisar</button>
        <span class="htmx-indicator">Analisando...</span>
      </div>
    </form>
    <pre id="compl-result"></pre>
  </div>

  <div class="card">
    <h2>Comparar regimes tributarios</h2>
    <form hx-on:submit="event.preventDefault();
          const f=this.faturamento.value, s=this.setor.value, fo=this.folha.value;
          const url='/v1/agentic/regimes?faturamento_anual='+f+'&setor='+s+
          (fo?'&folha_pagamento_anual='+fo:'');
          htmx.ajax('GET',url,{target:'#reg-result',swap:'innerHTML'});">
      <div class="row" style="flex-wrap:wrap;">
        <input name="faturamento" type="number" placeholder="Faturamento anual (R$)"
               required min="1" style="min-width:160px;">
        <select name="setor" required style="background:#0f172a; color:var(--fg);
                border:1px solid var(--border); padding:0.6rem; border-radius:6px;">
          <option value="serviços">Servicos</option>
          <option value="comércio">Comercio</option>
          <option value="indústria">Industria</option>
        </select>
        <input name="folha" type="number" placeholder="Folha anual (opcional)"
               min="0" style="min-width:160px;">
        <button type="submit">Comparar</button>
      </div>
    </form>
    <pre id="reg-result"></pre>
  </div>

  <div class="footer">
    <p>Dados de BrasilAPI, ReceitaWS, IBGE e fontes publicas |
       <a href="/docs">OpenAPI docs</a> |
       <a href="https://github.com/DeHor-Labs/mcp-fiscal-brasil">GitHub</a></p>
  </div>
</div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root() -> HTMLResponse:
    """Web UI demo (htmx)."""
    return HTMLResponse(_DEMO_HTML)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run() -> None:
    """Entry point para o comando `mcp-fiscal-api`."""
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("mcp_fiscal_brasil.api:app", host=host, port=port, reload=False)
