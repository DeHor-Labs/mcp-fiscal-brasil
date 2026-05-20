# Validacao de fornecedor no ERP

Integracao com sistemas ERP para validar fornecedores antes de emissao de NFe.

## Cenario

Antes de emitir NFe contra um CNPJ destinatario, voce quer confirmar que:

1. CNPJ existe e esta ativo
2. Empresa nao foi baixada / suspensa
3. Endereco bate com o cadastro
4. Atividade (CNAE) e compativel com a operacao

## Pre-emissao via webhook

```python
from fastapi import FastAPI, HTTPException
from mcp_fiscal_brasil.agentic import analyze_cnpj_compliance

app = FastAPI()

@app.post("/erp/pre-emissao-nfe")
async def validar_destinatario(payload: dict) -> dict:
    cnpj_destinatario = payload["cnpj_destinatario"]
    report = await analyze_cnpj_compliance(cnpj_destinatario)

    if report.risco_geral == "critico":
        raise HTTPException(
            status_code=409,
            detail={
                "blocked": True,
                "reason": report.resumo_executivo,
                "achados": [a.titulo for a in report.achados],
            },
        )

    return {
        "allowed": True,
        "score": report.score,
        "risco": report.risco_geral,
    }
```

## Conciliacao em lote (mensal)

```python
import asyncio
from datetime import datetime

async def reconciliacao_fornecedores(cnpjs_ativos: list[str]) -> dict:
    """Roda 1x por mes para reavaliar fornecedores ativos."""
    sem = asyncio.Semaphore(20)

    async def _avaliar(cnpj: str):
        async with sem:
            try:
                report = await analyze_cnpj_compliance(cnpj)
                return cnpj, report
            except Exception as e:
                return cnpj, {"error": str(e)}

    resultados = await asyncio.gather(*(_avaliar(c) for c in cnpjs_ativos))

    alertas = [
        (cnpj, r) for cnpj, r in resultados
        if hasattr(r, "risco_geral") and r.risco_geral in ("alto", "critico")
    ]

    if alertas:
        await notificar_compliance_team(alertas)

    return {
        "data": datetime.now().isoformat(),
        "total": len(cnpjs_ativos),
        "alertas": len(alertas),
    }
```

## Renovacao automatica de certidoes

```python
from mcp_fiscal_brasil.certidoes.tools import (
    consultar_certidao_federal,
    consultar_certidao_fgts,
)

async def renovar_certidoes(cnpj: str) -> dict:
    """Obtem URLs atualizadas de certidoes negativas."""
    federal = await consultar_certidao_federal(cnpj)
    fgts = await consultar_certidao_fgts(cnpj)
    return {"federal": federal, "fgts": fgts}
```

!!! note "Sobre certidoes"

    O `mcp-fiscal-brasil` retorna **URLs para emissao** das certidoes (CND, FGTS, CNDT). A emissao em si requer captcha / login no portal correspondente - nao automatizamos isso por questoes legais e de tos. Use os URLs para guiar o usuario / contador.

## Logs estruturados

```python
import structlog

log = structlog.get_logger()

log.info(
    "pre_emission_validation",
    cnpj_destinatario=cnpj,
    score=report.score,
    risco=report.risco_geral,
    decision="allowed" if report.risco_geral != "critico" else "blocked",
)
```

Ideal para BI: tracker de "quantos cadastros foram bloqueados", "qual a media de score por mes", etc.
