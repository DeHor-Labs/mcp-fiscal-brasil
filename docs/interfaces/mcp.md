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

## Ferramentas registradas (45)

| Categoria | Ferramentas |
|-----------|-------------|
| Agênticas | `analyze_cnpj_compliance`, `risk_score_supplier`, `consultar_empresas_lote`, `validate_nfe_full`, `summarize_sped` |
| CNPJ e cadastro | `consultar_cnpj`, `consultar_empresa_completa`, `consultar_simples_nacional`, `consultar_status_mei`, `consultar_cnae`, `buscar_cnae`, `validar_cpf`, `listar_cnpjs_por_nome` |
| NF-e, NFC-e e CT-e | `validar_chave_nfe`, `parse_nfe_xml`, `gerar_danfe`, `validar_assinatura_nfe`, `consultar_nfe`, `consultar_nfce`, `consultar_status_sefaz`, `baixar_nfe_distribuicao`, `manifestar_nfe` |
| Reforma Tributária e regimes | `simular_transicao_reforma_tributaria`, `compare_tax_regimes` |
| SPED e eSocial | `analisar_sped`, `listar_registros_sped`, `listar_eventos_esocial`, `validar_evento_esocial` |
| Tabelas fiscais offline | `consultar_ncm`, `consultar_cfop`, `validar_cst`, `consultar_cest`, `consultar_aliquota_icms` |
| Importação | `consultar_aliquotas_importacao`, `calcular_tributos_importacao` |
| Banco Central | `taxa_selic`, `ipca_periodo`, `ptax_data`, `calcular_correcao_monetaria` |
| NFS-e, certidões e localidades | `consultar_nfse`, `consultar_certidao_federal`, `consultar_certidao_fgts`, `consultar_cep`, `consultar_municipios_ibge`, `consultar_estado_ibge` |

## Configuracao do cliente

Veja [Configuracao](../getting-started/config.md#cliente-mcp) para exemplos de Claude Desktop, Claude Code, Cursor.

## Exemplos de uso

Apos configurar o servidor no cliente, pergunte em linguagem natural:

> "Consulte o CNPJ 12.345.678/0001-90 e me da o relatório de compliance completo"

O agente IA vai chamar `analyze_cnpj_compliance` automaticamente.
