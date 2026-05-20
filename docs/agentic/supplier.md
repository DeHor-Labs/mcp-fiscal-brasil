# risk_score_supplier

Score de risco para due diligence de fornecedor.

## Assinatura

```python
async def risk_score_supplier(
    cnpj: str,
    criterios_estritos: bool = False,
) -> SupplierRiskScore
```

## O que faz

Baseia-se em [`analyze_cnpj_compliance`](compliance.md) e aplica ajustes mais conservadores para contexto de **contratacao**:

- Achados com severidade `alto`/`critico` reduzem score em 15
- Achados `medio` reduzem em 5
- `criterios_estritos=True` reduz score em 10 (politicas anti-corrupcao)

Retorna **recomendacao binaria/quaternaria** acionavel.

## Schema de saida

```python
class SupplierRiskScore(BaseModel):
    cnpj: str
    razao_social: str
    risco: Literal["baixo", "medio", "alto", "critico"]
    score: int  # 0-100
    fatores: list[str]  # positivos e negativos
    recomendacao: Literal[
        "aprovar",
        "aprovar_com_ressalvas",
        "investigar",
        "recusar",
    ]
    data_analise: date
```

## Faixas de recomendacao

| Score | Recomendacao |
|-------|--------------|
| 80-100 | `aprovar` |
| 60-79 | `aprovar_com_ressalvas` |
| 30-59 | `investigar` |
| 0-29 | `recusar` |

## Exemplos

### CLI

```bash
mcp-fiscal supplier 12345678000190
mcp-fiscal supplier 12345678000190 --estrito --json
```

### Python (integracao com cadastro de fornecedores)

```python
async def cadastrar_fornecedor(cnpj: str) -> bool:
    score = await risk_score_supplier(cnpj, criterios_estritos=True)
    if score.recomendacao == "recusar":
        log.warning("supplier_rejected", cnpj=cnpj, fatores=score.fatores)
        return False
    if score.recomendacao == "investigar":
        await notificar_compliance_team(cnpj, score)
    return True
```

### Via agente IA

> "Faz a due diligence completa do CNPJ 12.345.678/0001-90 com criterios estritos e me da a recomendacao"
