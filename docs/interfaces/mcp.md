# Servidor MCP

O servidor MCP (Model Context Protocol) e a interface canonica para integrar com agentes IA (Claude, Cursor, qualquer cliente MCP).

## Executar

```bash
# stdio (padrao para clientes MCP)
mcp-fiscal-brasil

# HTTP
mcp-fiscal-brasil --transport http --port 8000

# SSE (deprecated mas ainda suportado)
mcp-fiscal-brasil --transport sse
```

## Ferramentas registradas (20+)

| Categoria | Ferramentas |
|-----------|-------------|
| CNPJ | `consultar_cnpj`, `listar_cnpjs_por_nome` |
| CPF | `validar_cpf` |
| NFe | `consultar_nfe`, `validar_chave_nfe`, `consultar_status_sefaz` |
| NFSe | `consultar_nfse` |
| SPED | `analisar_sped`, `listar_registros_sped` |
| eSocial | `listar_eventos_esocial`, `validar_evento_esocial` |
| Certidoes | `consultar_certidao_federal`, `consultar_certidao_fgts` |
| Simples | `consultar_simples_nacional` |
| **Agentic** | `analyze_cnpj_compliance`, `compare_tax_regimes`, `risk_score_supplier`, `validate_nfe_full`, `summarize_sped` |

## Configuracao do cliente

Veja [Configuracao](../getting-started/config.md#cliente-mcp) para exemplos de Claude Desktop, Claude Code, Cursor.

## Exemplos de uso

Apos configurar o servidor no cliente, pergunte em linguagem natural:

> "Consulte o CNPJ 12.345.678/0001-90 e me da o relatorio de compliance completo"

O agente IA vai chamar `analyze_cnpj_compliance` automaticamente.
