# Due diligence fiscal de fornecedores (lote)

Quando o time cadastra dezenas de fornecedores/mês, a revisão manual de cada CNPJ vira gargalo.

## Objetivo

- Padronizar decisão fiscal inicial para novos cadastros
- Reduzir risco de erro operacional e fraudes óbvias
- Criar trilha de auditoria para revisões futuras

Com `mcp-fiscal-brasil`, isso vira uma rotina de dados + regra em poucos passos.

## Exemplo de lote

```python
from mcp_fiscal_brasil.agentic import consultar_empresas_lote


async def avaliar_em_massa(cnpjs: list[str]) -> dict[str, list[str]]:
    lote = await consultar_empresas_lote(cnpjs, criterios_estritos=True)

    aprovados: list[str] = []
    bloqueados_ou_revisao: list[str] = []

    for item in lote.resultados:
        score = item.score_fornecedor
        if score is None or score.recomendacao in {"investigar", "recusar"}:
            bloqueados_ou_revisao.append(item.cnpj)
        else:
            aprovados.append(item.cnpj)

    return {
        "aprovados": aprovados,
        "bloqueados_ou_em_revisao": bloqueados_ou_revisao,
        "erros": lote.erros,
    }
```

## Exemplo com observabilidade mínima

```python
from mcp_fiscal_brasil.agentic import analyze_cnpj_compliance
import structlog

log = structlog.get_logger()


async def registrar_decisao(cnpj: str) -> None:
    score = await analyze_cnpj_compliance(cnpj)
    log.info(
        "due_diligence_completed",
        cnpj=score.cnpj,
        risco=score.risco_geral,
        score=score.score,
        achados=len(score.achados),
        fontes=score.fontes_consultadas,
    )
```

## Padrão de resposta (esperado)

Saída do workflow de due diligence:

- `status` de aprovação (`aprovar`, `aprovar_com_ressalvas`, `investigar`, `recusar`)
- `score` 0-100 para trilha de risco
- `fatores` com explicações naturais + acionáveis
- `fontes_consultadas` para rastreabilidade

## Trade-offs e limites

- Não há validação automática de reputação/AML nesta versão.
- A API atual retorna dados de `certidoes` como orientações/links quando necessário.
- Consistência dos dados depende de consulta externa; previna picos com cache e limite de concorrência.
