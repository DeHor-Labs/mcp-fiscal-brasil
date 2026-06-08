1/7
O sistema fiscal brasileiro é um dos mais complexos do mundo. Integrar dados de CNPJ, NFe e SPED em fluxos de trabalho de IA sempre foi um desafio técnico. Para resolver isso, criei o MCP Fiscal Brasil, o primeiro servidor MCP dedicado ao nosso ecossistema.

2/7
O Model Context Protocol (MCP) permite que assistentes como Claude e Cursor utilizem ferramentas externas de forma nativa. Com este servidor, você pode consultar dados fiscais diretamente no seu chat ou terminal sem precisar de chaves de API complexas ou integrações manuais.

3/7
O que ele faz hoje?
- Consulta completa de CNPJ (QSA, CNAE, Endereço)
- Status de optante pelo Simples Nacional e MEI
- Validação offline de chaves NFe (dígitos e estrutura)
- Status de disponibilidade do SEFAZ por estado
- Analisador de arquivos SPED (EFD/ECD)

4/7
A instalação é direta via pip. Se você usa o Claude Code, basta um comando para adicionar todas as 14 ferramentas fiscais ao seu assistente. Ele cuida da comunicação com BrasilAPI e SEFAZs de forma transparente.

5/7
Um caso de uso real: Auditoria. Você pode pedir para a IA analisar uma chave de nota fiscal ou um arquivo SPED e identificar inconsistências estruturais antes mesmo de enviar para o banco de dados. Tudo validado localmente.

6/7
Além de servidor MCP, ele funciona como SDK Python. Você pode importar o FiscalBrasil no seu projeto FastAPI ou Django para validações rápidas e consultas de dados públicos da Receita Federal.

7/7
O projeto é 100% open source (MIT). O objetivo é democratizar o acesso a dados fiscais para desenvolvedores brasileiros que estão construindo a nova geração de ferramentas baseadas em IA. 🇧🇷

Confira no GitHub: https://github.com/DeHor-Labs/mcp-fiscal-brasil
