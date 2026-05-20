# Modulo NFe

Notas Fiscais Eletronicas: consulta, validacao de chave, parse de XML.

## Tools MCP

- `consultar_nfe(chave_acesso)` - dados da NFe pela chave de 44 digitos
- `validar_chave_nfe(chave_acesso)` - validacao do DV (modulo 11)
- `consultar_status_sefaz(uf)` - status do webservice SEFAZ por UF

## Parser XML

```python
from mcp_fiscal_brasil.nfe.xml_parser import parse_nfe_xml

with open("nota.xml", "rb") as f:
    nfe = parse_nfe_xml(f.read(), chave="")
print(nfe.emitente.razao_social)
print(nfe.totais.valor_nota)
```

## Tool agentic

Para validacao consolidada (XML + chave + emissor), use [`validate_nfe_full`](../agentic/nfe.md).

## Compatibilidade

- Layout: NFe 4.00 (atual desde 2018)
- Namespaces: `http://www.portalfiscal.inf.br/nfe` (com fallback para sem namespace)
- Mensagens SEFAZ: padrao nacional + Portal Nacional NFe
