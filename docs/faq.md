# Perguntas frequentes

## Preciso de conta ou chave para começar?

Não para o fluxo básico. As consultas públicas e os recursos offline podem ser usados após a instalação. Algumas integrações específicas, como acesso mTLS à SEFAZ, exigem certificado A1 e configuração própria.

## O MCP Fiscal substitui a análise de um contador?

Não. O projeto organiza consultas, validações e sinais de risco para apoiar uma decisão. Regimes especiais, benefícios estaduais, interpretação jurídica e situações concretas ainda precisam de revisão profissional.

## Quais dados são enviados para serviços externos?

Depende da ferramenta. Parsing de XML, tabelas embarcadas e algumas validações rodam localmente. Consultas cadastrais usam as fontes indicadas na documentação de cada módulo. Revise a origem e a política de dados antes de usar informações pessoais ou fiscais em produção.

## Posso usar em lote ou dentro de um ERP?

Sim. O projeto oferece servidor MCP, CLI, SDK Python e REST API. Para volume, aplique limites de concorrência, registre a origem de cada resposta e trate indisponibilidade ou rate limit das fontes como erro recuperável.

## O resultado de uma consulta é sempre atual?

Não. A atualização depende da fonte pública consultada e do cache configurado. O consumidor deve guardar o horário da consulta e evitar apresentar uma resposta histórica como situação atual.

## O projeto emite certidões ou documentos fiscais?

Não como regra geral. Há validação e processamento de documentos já existentes, além de links para fontes oficiais. A emissão de certidões e obrigações continua nos canais competentes.

## Como avaliar antes de colocar em produção?

Escolha um único caso de uso, rode exemplos controlados, compare a saída com a fonte oficial e defina o comportamento para timeout, dado ausente e divergência. Depois disso, expanda o fluxo gradualmente.
