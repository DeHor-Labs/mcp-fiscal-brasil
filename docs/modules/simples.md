# Modulo Simples Nacional

Consulta de regime tributario Simples Nacional via API publica da Receita.

## Uso

```python
from mcp_fiscal_brasil.simples.client import SimplesClient

client = SimplesClient()
status = await client.get_simples_status("12345678000190")
print(status.optante)        # True/False
print(status.data_opcao)     # date | None
print(status.data_exclusao)  # date | None
```

## Tool MCP

- `consultar_simples_nacional(cnpj)` - dados completos

## Limitacoes

A API publica retorna apenas:

- Optante (sim/nao)
- Datas de opcao / exclusao
- Modalidade (MEI ou Simples)

**Nao retorna**: anexo, faixa atual, valor recolhido. Para isso, e necessario acesso autenticado ao Portal do Simples Nacional.
