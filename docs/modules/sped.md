# Modulo SPED

Parse e analise de arquivos SPED (Sistema Publico de Escrituracao Digital).

## Tipos suportados

- **EFD-ICMS-IPI** (SPED Fiscal)
- **EFD-Contribuicoes** (PIS/COFINS)
- **ECD** (Escrituracao Contabil Digital)
- **ECF** (Escrituracao Contabil Fiscal)

## Uso

```python
from mcp_fiscal_brasil.sped.tools import analisar_sped, listar_registros_sped

with open("sped_fiscal.txt", encoding="latin-1") as f:
    conteudo = f.read()

analise = await analisar_sped(conteudo, "sped_fiscal.txt")
print(f"Tipo: {analise.tipo_sped}")
print(f"Periodo: {analise.resumo.periodo_inicial} - {analise.resumo.periodo_final}")
print(f"Total: {analise.resumo.total_registros}")

# Listar todos os registros C100 (documentos fiscais)
docs = await listar_registros_sped(conteudo, "C100")
```

## Tools MCP

- `analisar_sped(conteudo, nome_arquivo?)` - parse e sumario
- `listar_registros_sped(conteudo, tipo_registro)` - filtra por tipo

## Tool agentic

Para sumario executivo de alto nivel, use [`summarize_sped`](../agentic/sped.md).

## Encoding

Arquivos SPED usam `latin-1`. Carregue assim:

```python
content = path.read_text(encoding="latin-1")
```
