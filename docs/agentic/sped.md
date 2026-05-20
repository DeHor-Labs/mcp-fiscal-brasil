# summarize_sped

Sumario executivo de arquivo SPED (Fiscal, Contribuicoes, ECF ou ECD).

## Assinatura

```python
async def summarize_sped(file_path: str | Path) -> SPEDSummary
```

## O que faz

1. Le o arquivo (encoding `latin-1`, padrao SPED)
2. Identifica tipo (EFD-ICMS-IPI, EFD-Contribuicoes, ECF, ECD)
3. Extrai periodo (registro 0000)
4. Extrai dados da empresa (CNPJ, razao social)
5. Conta registros totais e por bloco
6. Lista inconsistencias estruturais
7. Produz resumo executivo em pt-BR

## Schema de saida

```python
class SPEDSummary(BaseModel):
    arquivo: str
    tipo: Literal["fiscal", "contribuicoes", "ecf", "ecd"]
    periodo_inicio: date | None
    periodo_fim: date | None
    total_registros: int
    total_blocos: int
    cnpj: str | None
    razao_social: str | None
    inconsistencias: list[str]
    metricas_chave: dict[str, float]
    resumo: str
```

## Exemplos

### CLI

```bash
# Sumario rapido
mcp-fiscal-api  # liga o servidor
curl -X POST http://localhost:8000/v1/sped/summarize \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/contabil/sped_fiscal_202412.txt"}'
```

### Python

```python
from mcp_fiscal_brasil.agentic import summarize_sped

resumo = await summarize_sped("/contabil/sped_fiscal_202412.txt")
print(resumo.resumo)
print(f"Total: {resumo.total_registros} registros em {resumo.total_blocos} blocos")
if resumo.inconsistencias:
    print(f"Alertas: {len(resumo.inconsistencias)}")
```

### Via agente IA

> "Analisa o arquivo SPED em /contabil/sped_fiscal_202412.txt e me da o sumario executivo"
