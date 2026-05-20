# Web UI demo

A rota `/` da REST API serve uma pagina demo interativa construida com htmx 2.0.

## Acesso

```bash
mcp-fiscal-api
# Abrir http://localhost:8000
```

## Demos disponiveis

### Consulta de CNPJ

Input: CNPJ com ou sem formatacao. Output: dados cadastrais completos.

### Compliance consolidado

Input: CNPJ. Output: relatorio com score 0-100, risco classificado e achados.

### Comparativo de regimes tributarios

Inputs: faturamento, setor, folha (opcional). Output: comparativo MEI/Simples/LP/LR com melhor opcao e economia.

## Stack

- **htmx 2.0** - reatividade sem JS bundle
- **Tailwind-like inline CSS** - dark mode nativo
- **Sem build step** - HTML servido direto pelo FastAPI

## Personalizar

A pagina e definida em `src/mcp_fiscal_brasil/api.py` como string `_DEMO_HTML`. Para customizar, edite la e reinicie o servidor.

Para uma SPA mais completa, considere construir um frontend separado consumindo a [REST API](rest-api.md).
