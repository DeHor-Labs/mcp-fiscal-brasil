# Modulo IBGE

Dados geograficos: municipios, UFs e codigos IBGE.

## Uso

```python
from mcp_fiscal_brasil.ibge.client import IBGEClient

client = IBGEClient()

# Listar UFs
ufs = await client.get_states()

# Detalhes de uma UF
go = await client.get_state("GO")

# Listar municipios de GO
municipios_go = await client.get_municipalities("GO")

# Municipio por codigo IBGE
goiania = await client.get_municipality(5208707)
```

## Fonte

API publica do IBGE: https://servicodados.ibge.gov.br/api/v1/localidades/

Sem rate limit conhecido, mas use cache para reduzir latencia (default TTL 5min).
