# Planejamento tributario

Como usar o `mcp-fiscal` para sugerir regime tributario a clientes ou para decisoes internas de planejamento.

## Cenario

Cliente / equipe pergunta: "Qual o melhor regime para meu cenario?". Tradicionalmente: pegar planilhas, calcular para cada regime, comparar. Tempo: 30-60 minutos.

Com `compare_tax_regimes`:

```python
plano = compare_tax_regimes(
    faturamento_anual=500_000,
    setor="servicos",
    folha_pagamento_anual=180_000,
)
```

Resposta em milissegundos com aliquota efetiva e imposto estimado por regime.

## Exemplo: assistente de planejamento

```python
from mcp_fiscal_brasil.agentic import compare_tax_regimes

def sugerir_regime(cenario: dict) -> dict:
    """Sugere regime tributario com base no cenario do cliente."""
    plano = compare_tax_regimes(
        faturamento_anual=cenario["faturamento"],
        setor=cenario["setor"],
        folha_pagamento_anual=cenario.get("folha"),
    )

    return {
        "recomendacao": plano.melhor_opcao,
        "economia_anual": plano.economia_anual_vs_pior,
        "ranking": [
            {
                "regime": o.regime,
                "imposto_anual": o.imposto_anual_estimado,
                "aplicavel": o.aplicavel,
            }
            for o in plano.opcoes
        ],
        "observacoes": plano.observacoes,
    }
```

## Cenarios comuns

### MEI vs Simples (microempresa de servicos)

```bash
mcp-fiscal regimes --faturamento 60000 --setor servicos --json
mcp-fiscal regimes --faturamento 100000 --setor servicos --json
```

Esperado: para faturamento <= R$ 81 mil, MEI tende a ser melhor (se a atividade for permitida). Acima disso, Simples.

### Fator R em servicos

```bash
# Folha alta -> Anexo III
mcp-fiscal regimes --faturamento 500000 --setor servicos --folha 200000

# Folha baixa -> Anexo V (mais caro)
mcp-fiscal regimes --faturamento 500000 --setor servicos --folha 30000
```

A diferenca de aliquota pode passar de 5pp.

### Industria grande (sem Simples)

```bash
mcp-fiscal regimes --faturamento 10000000 --setor industria --json
```

Simples saira como `aplicavel=false`. Comparativo entre Lucro Presumido e Lucro Real.

## Integracao com SaaS contabil

```python
from fastapi import FastAPI
from mcp_fiscal_brasil.agentic import compare_tax_regimes

app = FastAPI()

@app.post("/api/planejamento-tributario")
async def planejamento(payload: dict) -> dict:
    plano = compare_tax_regimes(
        faturamento_anual=payload["faturamento"],
        setor=payload["setor"],
        folha_pagamento_anual=payload.get("folha"),
    )
    return plano.model_dump(mode="json", exclude_none=True)
```

## Limitacoes

- Calculo simplificado, **NAO substitui parecer contabil**
- Nao considera beneficios estaduais (ProEmprego, regimes especiais)
- ICMS usado e media nacional (12%) - na pratica varia 4-25% por UF
- ISS usado e media (5%) - varia 2-5% por municipio
- Aliquotas atualizadas em 2025; revisar a cada reforma tributaria
