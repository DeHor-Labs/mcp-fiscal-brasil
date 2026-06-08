# Tools agenticas

Conjunto de ferramentas desenhado para uso por agentes de IA e serviços automatizados.

Cada tool combina múltiplas fontes e já entrega uma estrutura pronta para decisão, incluindo score, risco e resumo.

## Catálogo (v0.2.x)

| Tool | Uso principal | Output principal |
|------|---------------|----------------|
| [`analyze_cnpj_compliance`](compliance.md) | Relatório fiscal consolidado de CNPJ | `risco_geral`, `score`, `achados`, `resumo_executivo` |
| [`compare_tax_regimes`](regimes.md) | Simulação de carga tributária entre regimes | Ranking por custo estimado + melhor cenário |
| [`risk_score_supplier`](supplier.md) | Due diligence de fornecedor para aprovação | Recomendação (`aprovar`, `aprovar_com_ressalvas`, `investigar`, `recusar`) |
| [`consultar_empresas_lote`](../use-cases/due-diligence.md) | Triagem de carteira de fornecedores | Compliance + score + erro por CNPJ em uma chamada |
| [`validate_nfe_full`](nfe.md) | Validação consolidada de XML de NFe | Validação estrutural, consistência da chave, situação do emissor |
| [`summarize_sped`](sped.md) | Sumário executivo de arquivo SPED | Período, registros, blocos, inconsistências e alertas |

## Quando usar cada uma

1. **Antes de contratar/registrar um fornecedor**
   1. `risk_score_supplier` para recomendação automática.
   2. `consultar_empresas_lote` quando houver carteira inteira para triar.
   3. `analyze_cnpj_compliance` para explicação dos achados, quando necessário.
   4. Guardar fatores, score e fonte no log de auditoria.

2. **Antes de aprovar entrada de nota**
   1. `validate_nfe_full` com o XML recebido.
   2. Bloquear automaticamente em `valida_estruturalmente=False` ou severidade crítica.

3. **Na rotina de fechamento**
   1. `summarize_sped` por período.
   2. Se houver inconsistências, direcionar revisão técnica antes do envio.

4. **Em reunião de planejamento tributário**
   1. `compare_tax_regimes` com faturamento, setor e folha.
   2. Exportar ranking e observações para discutir com contador.

## Contratos e comportamento

=== "Tolerância a falhas"

    - `analyze_cnpj_compliance` pode seguir com fontes parciais (Simples/MEI), mas depende de CNPJ válido e consulta principal.
    - `validate_nfe_full` retorna lista de issues e ainda pode seguir com dados úteis do XML.
    - `summarize_sped` também funciona com arquivo SPED íntegro mínimo; inconsistências aparecem em `inconsistencias`.

=== "Restrições técnicas"

    - `risk_score_supplier` é uma avaliação de risco; não faz KYC, sanctions check ou onboarding final sozinho.
    - `validate_nfe_full` **não** substitui assinatura digital avançada, eventos NFe ou validação XSD completa.
    - `compare_tax_regimes` é estimativa simplificada para decisão preliminar (ex.: sem benefícios estaduais/regimes especiais).
    - `analyze_cnpj_compliance` orienta; certidões orientativas são links, não emissão automática.

## Exemplo integrado (1 fluxo, 1 resposta)

```python
async def compliance_gate(cnpj: str, nfe_xml_path: str | None = None) -> dict[str, str]:
    """Gate de onboarding + documento fiscal numa chamada de contexto."""
    supplier = await risk_score_supplier(cnpj, criterios_estritos=True)
    report = await analyze_cnpj_compliance(cnpj)

    if not nfe_xml_path:
        return {
            "status": "pendente",
            "recomendacao": supplier.recomendacao,
            "justificativa": report.resumo_executivo,
        }

    nfe = await validate_nfe_full(nfe_xml_path)
    return {
        "status": "aprovado" if nfe.chave_consistente else "bloqueado",
        "fornecedor": supplier.recomendacao,
        "fornecedor_score": str(supplier.score),
        "nfe": nfe.resumo,
        "risco_fornecedor": report.risco_geral,
    }
```

## Casos de uso recomendados

- [Due diligence em lote de fornecedores](../use-cases/due-diligence.md)
- [Validação de fornecedores no ERP](../use-cases/supplier-validation.md)
- [Planejamento tributário com cenários](../use-cases/tax-planning.md)
- [Relatório de compliance consolidado](../use-cases/compliance-report.md)
