# Relatório de compliance consolidado

Esse caso de uso cobre análise fiscal de entidade para decisão de negócio, sem substituir a conclusão contábil formal.

## Quando usar

- Aprovação de cadastro de cliente/fornecedor
- Due diligence pontual antes de assinatura de contrato
- Geração de contexto inicial para comitê interno de risco

## Saída esperada

`analyze_cnpj_compliance` retorna:

- `risco_geral`: baixo/médio/alto/crítico
- `score` (0–100)
- `achados`: com categoria, severidade e recomendação
- `fontes_consultadas`: quais serviços responderam no momento da análise

## Exemplo em Python

```python
from mcp_fiscal_brasil.agentic import analyze_cnpj_compliance


async def carregar_relatorio(cnpj: str) -> dict[str, object]:
    report = await analyze_cnpj_compliance(cnpj)
    return {
        "cnpj": report.cnpj,
        "razao_social": report.razao_social,
        "risco_geral": report.risco_geral,
        "score": report.score,
        "resumo": report.resumo_executivo,
        "achados": [
            {
                "categoria": achado.categoria,
                "severidade": achado.severidade,
                "titulo": achado.titulo,
                "recomendacao": achado.recomendacao,
            }
            for achado in report.achados
        ],
        "fontes": report.fontes_consultadas,
    }
```

## Exemplo de REST

```bash
curl "http://localhost:8000/v1/agentic/compliance/12345678000190"
```

## Limites de escopo (importante)

- A análise atual combina dados de CNPJ, Simples, MEI e CNAE.
- Certidões de débitos aparecem como apoio de consulta; não há validação de emissão automática.
- Fatos de terceiros (QSA incompleta, endereço incompleto) entram como fator de risco/alerta e devem ser tratados conforme política interna.
