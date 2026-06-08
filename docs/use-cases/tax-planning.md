# Planejamento tributário com simulação de regime

Esse fluxo ajuda a responder perguntas comerciais com resposta rápida: "qual regime é mais econômico para este cenário?".

## O que comparar

`compare_tax_regimes` gera:

- Regime aplicável ou motivo de não aplicabilidade
- Aliquota e imposto anual estimado (simplificado)
- Melhor cenário e economia versus pior cenário aplicável
- Explicações objetivas de hipótese usada

## Exemplo em Python

```python
from mcp_fiscal_brasil.agentic import compare_tax_regimes


def comparar(cenario: dict) -> dict[str, object]:
    plano = compare_tax_regimes(
        faturamento_anual=cenario["faturamento_anual"],
        setor=cenario["setor"],
        folha_pagamento_anual=cenario.get("folha_pagamento_anual"),
    )

    return {
        "melhor_opcao": plano.melhor_opcao,
        "economia_anual_vs_pior": plano.economia_anual_vs_pior,
        "resumo": [
            {
                "regime": item.regime,
                "aplicavel": item.aplicavel,
                "imposto": item.imposto_anual_estimado,
                "aliquota": item.aliquota_efetiva_estimada,
                "pros": item.pros,
                "contras": item.contras,
            }
            for item in plano.opcoes
        ],
    }
```

## Exemplo via REST

```bash
curl "http://localhost:8000/v1/agentic/regimes?faturamento_anual=500000&setor=serviços&folha_pagamento_anual=180000"
```

## Onde usar em produto

- Pré-venda de serviços e precificação
- Onboarding de clientes PME com cenário de crescimento
- Apoio de decisão antes de consulta formal com contador

## Limitações importantes

- Não considera benefícios estaduais, regimes especiais ou particularidades de ISS por município.
- Usa premissas médias de ICMS/ISS e tabelas públicas (2025) para estimativa rápida.
- Não substitui análise contábil final; para fechamento fiscal formal, valide com contador.
