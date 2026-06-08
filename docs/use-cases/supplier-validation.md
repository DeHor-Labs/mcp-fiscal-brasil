# Validar fornecedor antes de emitir/receber documento

Cenário típico: qualquer operação com terceiros (compra, pagamento, emissão de NFe) precisa de uma validação fiscal rápida antes de aprovar cadastro.

## Fluxo recomendado

1. Validar sintaticamente o CNPJ (opcional localmente).
2. Rodar `risk_score_supplier` para risco geral e recomendação.
3. Em caso de recomendação não conclusiva, complementar com `analyze_cnpj_compliance`.
4. Registrar decisão em trilha de auditoria.

```mermaid
flowchart TD
    A[Evento do ERP] --> B[normalizar CNPJ]
    B --> C[risk_score_supplier]
    C --> D{recomendação}
    D -->|aprovar| E[Aprovação automática]
    D -->|aprovar_com_ressalvas| F[Aprovação com flag + notificação]
    D -->|investigar| G[Fila manual + consulta humana]
    D -->|recusar| H[Bloqueio + motivo]
    C --> I[analyze_cnpj_compliance (opcional)]
    I --> J[log de achados]
```

## Exemplo prático com Python

```python
from mcp_fiscal_brasil.agentic import risk_score_supplier, analyze_cnpj_compliance
import structlog

log = structlog.get_logger()


async def avaliar_fornecedor(cnpj: str) -> dict[str, object]:
    score = await risk_score_supplier(cnpj, criterios_estritos=True)
    if score.recomendacao in {"investigar", "recusar"}:
        report = await analyze_cnpj_compliance(cnpj)
    else:
        report = None

    log.info(
        "supplier_evaluated",
        cnpj=cnpj,
        score=score.score,
        risco=score.risco,
        recomendacao=score.recomendacao,
        fatores=score.fatores,
        report_fontes=getattr(report, "fontes_consultadas", None),
    )

    return {
        "cnpj": score.cnpj,
        "recomendacao": score.recomendacao,
        "score": score.score,
        "riscos": score.fatores,
        "resumo_compliance": None if report is None else report.resumo_executivo,
    }
```

## REST sem código

```bash
# 1) Score resumido
curl -s "http://localhost:8000/v1/agentic/supplier/12345678000190?estrito=true"

# 2) Compliance completo (caso necessário)
curl -s "http://localhost:8000/v1/agentic/compliance/12345678000190"
```

## Escopo técnico (o que realmente roda hoje)

- `risk_score_supplier` aplica redução de score por achados críticos/médios e retorna recomendação.
- O score nasce de `analyze_cnpj_compliance` e de regras conservadoras.
- Não há verificação de contas/cadastro positivo/negativo em órgão central além de CNPJ, Simples e MEI.
- Para certidões (FGTS/CND/etc.), a resposta atual pode incluir URL de consulta, não emissão automática.

## Sinais que aceleram o gate de aprovação

- `risco == "baixo"` e fatores sem severidade alta -> aprovação sem revisão
- `risco == "medio"` com fatores estáveis por período -> aprovação com ressalva
- `recusar` ou `investigar` -> encaminhar fila de revisão e manter trilha de justificativa estruturada
