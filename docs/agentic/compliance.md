# analyze_cnpj_compliance

Analise consolidada de compliance fiscal de um CNPJ.

## Assinatura

```python
async def analyze_cnpj_compliance(cnpj: str) -> ComplianceReport
```

## O que faz

Consulta **em paralelo**:

1. Dados cadastrais (Receita Federal via BrasilAPI / ReceitaWS)
2. Regime Simples Nacional
3. Status MEI
4. CNAE principal e secundarios

Aplica heuristicas e retorna um relatorio unico com:

- **`risco_geral`** (`baixo` / `medio` / `alto` / `critico`)
- **`score`** (0-100, calibrado: 90 = excelente, 5 = critico)
- **`achados`** detalhados por categoria
- **`resumo_executivo`** em pt-BR para apresentar a humano
- **`fontes_consultadas`** que responderam com sucesso

## Schema de saida

```python
class ComplianceReport(BaseModel):
    cnpj: str
    razao_social: str
    risco_geral: Literal["baixo", "medio", "alto", "critico"]
    score: int  # 0-100
    achados: list[ComplianceFinding]
    resumo_executivo: str
    fontes_consultadas: list[str]
```

## Tolerancia a falhas

Se uma das fontes (Simples, MEI) estiver offline, a tool **nao falha**. So a fonte CNPJ e mandatoria (se ela falhar, a tool levanta `RuntimeError`). As demais sao usadas se disponiveis.

Verifique `fontes_consultadas` para saber quais responderam.

## Heuristica de risco

| Sinal | Severidade |
|-------|-----------|
| Situacao `BAIXADA` ou `NULA` | critico |
| Situacao `INAPTA` | alto |
| Situacao `SUSPENSA` | medio |
| Endereco incompleto | medio |
| QSA nao disponivel | medio |
| Tudo regular | baixo |

Risco geral = severidade maxima dos achados.

## Exemplos

### CLI

```bash
mcp-fiscal compliance 12345678000190
mcp-fiscal compliance 12345678000190 --json | jq '.score'
```

### REST API

```bash
curl http://localhost:8000/v1/agentic/compliance/12345678000190
```

### Python

```python
import asyncio
from mcp_fiscal_brasil.agentic import analyze_cnpj_compliance

async def main():
    report = await analyze_cnpj_compliance("12345678000190")
    print(report.resumo_executivo)
    for achado in report.achados:
        print(f"- [{achado.severidade}] {achado.titulo}")

asyncio.run(main())
```

### Via agente IA

> "Analise o compliance fiscal do CNPJ 12.345.678/0001-90 e me responda em portugues"
