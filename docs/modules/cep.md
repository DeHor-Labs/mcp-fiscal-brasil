# Modulo CEP

Lookup de enderecos por CEP.

## Uso

```python
from mcp_fiscal_brasil.cep.client import CEPClient

client = CEPClient()
endereco = await client.get_address("74000000")
print(f"{endereco.logradouro}, {endereco.bairro} - {endereco.municipio}/{endereco.uf}")
```

## Fontes

- **BrasilAPI** (preferencial)
- **ViaCEP** (fallback)

Ambas sao publicas e gratuitas, sem rate limit estrito.
