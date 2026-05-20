# Quickstart

5 minutos para sentir o que o `mcp-fiscal-brasil` faz.

## 1. Consulta CNPJ via CLI

```bash
mcp-fiscal cnpj 00000000000191
```

Saida:

```
cnpj: 00000000000191
razao_social: BANCO DO BRASIL S.A.
nome_fantasia: BB
situacao_cadastral: ATIVA
natureza_juridica: 2038
porte: DEMAIS
capital_social: ...
endereco:
  logradouro: SAUN QUADRA 5 LOTE B TORRES I, II E III
  municipio: BRASILIA
  uf: DF
  cep: 70040912
atividade_principal:
  codigo: 6422100
  descricao: Bancos multiplos, com carteira comercial
origem: BrasilAPI
```

## 2. Analise de compliance consolidada

Combina CNPJ + Simples + MEI + CNAE em uma chamada:

```bash
mcp-fiscal compliance 00000000000191
```

Saida tipica:

```
cnpj: 00000000000191
razao_social: BANCO DO BRASIL S.A.
risco_geral: baixo
score: 90
achados:
  - categoria: atividade
    severidade: baixo
    titulo: CNAE principal 6422100
    detalhe: Bancos multiplos, com carteira comercial
resumo_executivo: CNPJ 00000000000191 (BANCO DO BRASIL S.A.) apresenta risco baixo (score 90/100)...
fontes_consultadas:
  - BrasilAPI
  - Simples Nacional
```

## 3. Compare regimes tributarios

Cenario: empresa de servicos, faturamento R$ 500 mil/ano, folha R$ 180 mil.

```bash
mcp-fiscal regimes --faturamento 500000 --setor servicos --folha 180000
```

Saida:

```
cenario_faturamento_anual: 500000
cenario_setor: servicos
folha_pagamento_anual: 180000
opcoes:
  - regime: simples_nacional
    aplicavel: True
    aliquota_efetiva_estimada: 16.0
    imposto_anual_estimado: 80000
  - regime: lucro_presumido
    aplicavel: True
    aliquota_efetiva_estimada: 19.8
    imposto_anual_estimado: 99000
melhor_opcao: simples_nacional
economia_anual_vs_pior: ...
```

## 4. REST API + Web UI demo

```bash
mcp-fiscal-api
# Servidor em http://localhost:8000
```

Abra no navegador:

- **`/`** - Web UI com 3 demos interativas
- **`/docs`** - OpenAPI / Swagger
- **`/v1/cnpj/00000000000191`** - JSON via HTTP

## 5. Como SDK Python

```python
import asyncio
from mcp_fiscal_brasil.agentic import (
    analyze_cnpj_compliance,
    compare_tax_regimes,
    risk_score_supplier,
)


async def main():
    # Compliance
    report = await analyze_cnpj_compliance("00000000000191")
    print(f"Risco: {report.risco_geral} (score {report.score}/100)")

    # Due diligence de fornecedor
    score = await risk_score_supplier("00000000000191", criterios_estritos=True)
    print(f"Recomendacao: {score.recomendacao}")

    # Planejamento tributario
    plano = compare_tax_regimes(
        faturamento_anual=500_000,
        setor="servicos",
        folha_pagamento_anual=180_000,
    )
    print(f"Melhor regime: {plano.melhor_opcao}")
    print(f"Economia anual: R$ {plano.economia_anual_vs_pior:,.2f}")


asyncio.run(main())
```

## 6. Com agentes IA (Claude, GPT, Gemini)

Apos configurar o servidor MCP no seu cliente ([config](config.md)), basta perguntar em linguagem natural:

> "Consulte o CNPJ 00.000.000/0001-91 e me da uma analise de compliance"
>
> "A empresa X esta apta a entrar no Simples Nacional?"
>
> "Compare os regimes tributarios para um servico com R$ 500 mil de faturamento e R$ 180 mil de folha"

O Claude/GPT/Gemini chama as tools certas e responde em pt-BR.

## Proximos passos

- [Tools agenticas detalhadas](../agentic/index.md)
- [REST API reference](../interfaces/rest-api.md)
- [Casos de uso reais](../use-cases/due-diligence.md)
