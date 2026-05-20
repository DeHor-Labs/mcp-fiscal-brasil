# Modulo CNAE

Classificacao Nacional de Atividades Economicas.

## Uso

```python
from mcp_fiscal_brasil.cnae.client import CNAEClient

client = CNAEClient()
atividades = await client.search("desenvolvimento de software")
for a in atividades:
    print(a.codigo, a.descricao)
```

## Schema

```python
class CNAEActivity(BaseModel):
    codigo: str
    descricao: str

class CNAEClass(BaseModel):
    classe: str
    descricao: str
    atividades: list[CNAEActivity]
```

## Casos de uso

- Validar compatibilidade entre atividade economica e operacao
- Sugerir CNAE para novos cadastros
- Mapear empresa -> setor para analise de carteira
