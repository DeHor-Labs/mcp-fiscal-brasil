# compare_tax_regimes

Comparativo entre regimes tributarios brasileiros (MEI, Simples, Lucro Presumido, Lucro Real).

## Assinatura

```python
def compare_tax_regimes(
    faturamento_anual: float,
    setor: Literal["comercio", "servicos", "industria"],
    folha_pagamento_anual: float | None = None,
) -> TaxRegimeComparison
```

## O que faz

Calcula **aliquota efetiva estimada** e **imposto anual estimado** para cada regime tributario aplicavel ao cenario, baseado em tabelas publicas vigentes (2025).

Retorna o regime **mais economico** e a **economia anual vs pior opcao**.

!!! warning "Estimativa, nao planejamento contabil"

    Calculo simplificado baseado em premissas publicas. NAO substitui parecer de contador. Use para direcionamento em decisoes de planejamento, nao para apuracao final.

## Heuristicas

### MEI
- Limite: R$ 81.000/ano
- Aplicavel apenas a algumas atividades
- Tributacao fixa mensal (~R$ 75-80)

### Simples Nacional
- Limite: R$ 4,8 milhoes/ano
- Anexo conforme setor (comercio I, industria II, servicos III ou V)
- **Fator R** (servicos): folha/faturamento >= 28% -> Anexo III (mais barato)

### Lucro Presumido
- Limite: R$ 78 milhoes/ano
- Presuncao 8% (comercio/industria) ou 32% (servicos)
- PIS/COFINS cumulativos (3,65%)

### Lucro Real
- Sem teto
- IRPJ 15% + adicional 10% sobre lucro liquido
- PIS/COFINS nao-cumulativos com creditos
- Burocracia maior

## Schema de saida

```python
class TaxRegimeComparison(BaseModel):
    cenario_faturamento_anual: float
    cenario_setor: Literal["comercio", "servicos", "industria"]
    folha_pagamento_anual: float | None
    opcoes: list[TaxRegimeOption]  # ordenadas: aplicaveis primeiro, do mais barato
    melhor_opcao: str
    economia_anual_vs_pior: float
    observacoes: str

class TaxRegimeOption(BaseModel):
    regime: Literal["mei", "simples_nacional", "lucro_presumido", "lucro_real"]
    aplicavel: bool
    motivo_inaplicavel: str | None
    aliquota_efetiva_estimada: float | None
    imposto_anual_estimado: float | None
    pros: list[str]
    contras: list[str]
```

## Exemplos

### Empresa de servicos pequena

```bash
mcp-fiscal regimes --faturamento 300000 --setor servicos --folha 120000 --json
```

Esperado: melhor opcao = `simples_nacional` (Anexo III pelo Fator R).

### Industria de medio porte

```bash
mcp-fiscal regimes --faturamento 5000000 --setor industria --folha 1500000 --json
```

Esperado: Simples Nacional **nao aplicavel** (faturamento > R$ 4,8 mi). Melhor opcao tipicamente `lucro_presumido`.

### Via REST API

```bash
curl "http://localhost:8000/v1/agentic/regimes?faturamento_anual=500000&setor=servicos&folha_pagamento_anual=180000"
```

### Via agente IA

> "Sou prestador de servicos com faturamento de R$ 500 mil e folha de R$ 180 mil. Qual o melhor regime?"
