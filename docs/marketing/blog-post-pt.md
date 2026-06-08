# Como usar IA para automatizar emissão e consulta de NFe com MCP

O sistema fiscal brasileiro é reconhecido internacionalmente pela sua complexidade. Com 27 Secretarias da Fazenda (SEFAZs), milhares de municípios com portais de NFSe distintos e uma carga constante de obrigações acessórias como SPED e eSocial, a conformidade fiscal consome uma parte significativa do tempo de desenvolvedores e contadores.

Até recentemente, integrar esses dados em fluxos de trabalho baseados em inteligência artificial exigia a criação de camadas intermediárias complexas, tratamento manual de captchas ou o desenvolvimento de wrappers para APIs governamentais que nem sempre seguem padrões modernos. O Model Context Protocol (MCP) muda essa dinâmica ao permitir que assistentes de IA se conectem diretamente a ferramentas especializadas.

Neste artigo, veremos como o projeto MCP Fiscal Brasil permite automatizar a consulta e validação de documentos fiscais diretamente de assistentes como Claude, Cursor ou interfaces de linha de comando.

## O Problema da Fragmentação Fiscal

Desenvolver software que lide com dados fiscais no Brasil significa enfrentar fragmentação. Cada estado possui seu próprio tempo de resposta para serviços de NFe. Cada prefeitura adota um padrão diferente para NFSe (Abrasf 1.0, 2.0, GissOnline, Betha, etc.). Quando um desenvolvedor precisa verificar se um CNPJ está ativo ou se uma nota fiscal é autêntica, ele geralmente precisa navegar por portais lentos ou contratar APIs pagas dispendiosas.

Essa fricção impede que a IA seja utilizada em seu potencial máximo para auditoria, automação de compras ou suporte jurídico, pois o modelo de linguagem (LLM) não tem "olhos" para o que está acontecendo nos sistemas da Receita Federal em tempo real.

## Introduzindo o MCP Fiscal Brasil

O MCP Fiscal Brasil é um servidor que implementa o Model Context Protocol, um padrão aberto que permite que modelos de IA usem ferramentas externas de forma segura e padronizada. Ao rodar este servidor localmente ou em sua infraestrutura, você concede ao seu assistente de IA a capacidade de executar funções como:

1. Consultar dados completos de um CNPJ (via BrasilAPI/ReceitaWS).
2. Verificar o status de optante pelo Simples Nacional ou MEI.
3. Validar chaves de acesso de NFe offline (verificando dígitos e estrutura).
4. Checar a disponibilidade dos servidores SEFAZ em cada estado.
5. Analisar a estrutura de arquivos SPED para identificar registros específicos.

## Demonstração Técnica

Uma vez instalado, o servidor expõe ferramentas que a IA pode chamar sob demanda. Veja como isso se traduz na prática.

### Configuração em 30 Segundos

Se você utiliza o Claude Code ou o Claude Desktop, a configuração é direta:

```bash
pip install mcp-fiscal-brasil
claude mcp add fiscal-brasil -- mcp-fiscal-brasil
```

A partir desse momento, você pode fazer perguntas técnicas ao assistente.

### Exemplo 1: Inteligência de Mercado e Compliance

Imagine que você está analisando um novo fornecedor. Em vez de copiar e colar dados manualmente, você simplesmente fornece o CNPJ:

**Usuário:** "Verifique o CNPJ 00.623.904/0001-97 e me diga se eles são optantes do Simples Nacional."

**IA (usando ferramentas do MCP):** "A empresa é a BANCO DO BRASIL S.A., fundada em 1808. De acordo com a consulta realizada, ela não é optante pelo Simples Nacional, operando sob o regime de tributação normal."

### Exemplo 2: Auditoria de Notas Fiscais

Para desenvolvedores trabalhando em sistemas de ERP ou e-commerce, validar chaves de NFe é uma tarefa comum. O MCP Fiscal Brasil permite que a IA faça isso instantaneamente:

**Usuário:** "Esta nota fiscal parece correta? 35240300623904000197550010000012341234567890"

**IA:** "A chave de acesso informada é estruturalmente válida. Ela refere-se a uma nota emitida em São Paulo (UF 35) em março de 2024 pelo CNPJ 00.623.904/0001-97. O dígito verificador está correto."

### Exemplo 3: Análise de Arquivos SPED

Auditar um arquivo SPED Fiscal manualmente é exaustivo. Com o MCP, você pode pedir para a IA listar registros específicos de um arquivo que você está editando no Cursor:

**Usuário:** "Analise o arquivo SPED aberto e identifique todos os registros C100."

**IA:** "Identifiquei 15 registros C100 no arquivo. O período de apuração é 01/2024. Aqui está o resumo dos valores..."

## Integração com SDK Python

Além do uso via servidor MCP, o projeto funciona como uma biblioteca Python tradicional (SDK). Isso permite que você utilize as mesmas validações e consultas em suas aplicações FastAPI ou Django:

```python
import asyncio
from mcp_fiscal_brasil import FiscalBrasil

async def validar_fornecedor(cnpj: str):
    async with FiscalBrasil() as fiscal:
        dados = await fiscal.consultar_cnpj(cnpj)
        return dados["situacao_cadastral"] == "ATIVA"

asyncio.run(validar_fornecedor("00.000.000/0001-91"))
```

## Conclusão

O MCP Fiscal Brasil não é apenas uma ferramenta de consulta, mas uma ponte que traz o sistema fiscal brasileiro para a era dos agentes de IA. Ao remover a complexidade de conexão com as APIs governamentais e fornecer ferramentas de validação offline, o projeto permite que desenvolvedores foquem no que realmente importa: construir soluções inteligentes e eficientes.

O projeto é de código aberto (MIT) e está disponível no GitHub. Se você trabalha com desenvolvimento voltado para o mercado brasileiro, este servidor MCP é um componente essencial para o seu toolkit.

**Nikolas de Hor**
Goiânia, GO, Brasil

---
### Como contribuir
O projeto está em fase de expansão. Planejamos suporte para emissão direta de notas (via certificado A1) e integração com mais de 50 prefeituras para NFSe. Sinta-se à vontade para abrir issues ou enviar pull requests no repositório oficial.

[Acesse o MCP Fiscal Brasil no GitHub](https://github.com/DeHor-Labs/mcp-fiscal-brasil)
