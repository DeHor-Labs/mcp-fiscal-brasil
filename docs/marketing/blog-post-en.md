# Bridging AI Assistants to Brazil's Fiscal APIs

Brazil is known for having one of the most complex tax and fiscal systems in the world. With 27 state-level tax authorities (SEFAZ), thousands of municipal portals for service invoices (NFSe), and a constant stream of mandatory digital reporting like SPED and eSocial, fiscal compliance is a significant burden for both local and international companies operating in the country.

Until recently, integrating these data streams into AI-driven workflows required building custom wrappers, handling legacy government portals, or paying for expensive third-party APIs. The Model Context Protocol (MCP) changes this by allowing AI assistants to connect directly to specialized fiscal tools.

In this article, we will explore how MCP Fiscal Brasil enables the automation of fiscal document consultation and validation directly from AI assistants like Claude, Cursor, or CLI environments.

## The Challenge of Fiscal Fragmentation

Building software that handles Brazilian fiscal data means dealing with extreme fragmentation. Each state has its own uptime and response patterns for Electronic Invoice (NFe) services. Each city adopts different standards for Service Invoices (NFSe). When a developer needs to verify if a CNPJ (Corporate Tax ID) is active or if an invoice is authentic, they usually have to navigate slow government portals or deal with inconsistent API responses.

This friction prevents AI from being used to its full potential for auditing, procurement automation, or legal support, as the Large Language Model (LLM) lacks direct access to what is happening in the Brazilian Federal Revenue systems in real-time.

## Introducing MCP Fiscal Brasil

MCP Fiscal Brasil is a server that implements the Model Context Protocol, an open standard that enables AI models to use external tools securely and consistently. By running this server locally or within your infrastructure, you grant your AI assistant the ability to:

1. Fetch complete corporate data for any CNPJ (via BrasilAPI/ReceitaWS).
2. Check tax regime status (Simples Nacional or MEI).
3. Validate NFe access keys offline (checking digits and structure).
4. Monitor the availability of SEFAZ servers across all Brazilian states.
5. Analyze the structure of SPED files to identify specific accounting records.

## Technical Walkthrough

Once installed, the server exposes tools that the AI can invoke on demand. Here is how this works in practice.

### Setup in 30 Seconds

If you are using Claude Code or Claude Desktop, configuration is straightforward:

```bash
pip install mcp-fiscal-brasil
claude mcp add fiscal-brasil -- mcp-fiscal-brasil
```

From this point on, you can ask your assistant technical questions about Brazilian entities or documents.

### Case 1: Vendor Intelligence and Compliance

Imagine you are vetting a new Brazilian vendor. Instead of manual data entry, you simply provide the CNPJ:

**User:** "Check CNPJ 00.623.904/0001-97 and tell me if they are currently in the Simples Nacional tax regime."

**AI (using MCP tools):** "The company is BANCO DO BRASIL S.A., founded in 1808. Based on the real-time query, they are not enrolled in Simples Nacional, operating under the standard corporate tax regime."

### Case 2: Invoice Validation

For developers working on ERPs or e-commerce platforms, validating NFe keys is a common task. MCP Fiscal Brasil allows the AI to perform this instantly:

**User:** "Does this invoice key look correct? 35240300623904000197550010000012341234567890"

**AI:** "The provided access key is structurally valid. It refers to an invoice issued in São Paulo (UF 35) in March 2024 by CNPJ 00.623.904/0001-97. The check digit is correct."

### Case 3: Auditing SPED Files

Auditing a SPED (Public Digital Bookkeeping System) file manually is exhausting. With MCP, you can ask the AI to list specific records from a file you are currently editing in Cursor:

**User:** "Analyze the open SPED file and identify all C100 records."

**AI:** "I identified 15 C100 records in the file. The reporting period is 01/2024. Here is a summary of the tax credits..."

## Python SDK Integration

Beyond the MCP server usage, the project also functions as a standard Python library (SDK). This allows you to use the same validations and queries in your FastAPI or Django applications:

```python
import asyncio
from mcp_fiscal_brasil import FiscalBrasil

async def validate_vendor(cnpj: str):
    async with FiscalBrasil() as fiscal:
        data = await fiscal.consultar_cnpj(cnpj)
        return data["situacao_cadastral"] == "ATIVA"

asyncio.run(validate_vendor("00.000.000/0001-91"))
```

## Conclusion

MCP Fiscal Brasil is not just a query tool; it is a bridge that brings the Brazilian fiscal system into the era of AI agents. By abstracting the complexity of government APIs and providing offline validation tools, the project allows developers to focus on building intelligent and efficient solutions.

The project is open-source (MIT) and available on GitHub. If you are developing software for the Brazilian market, this MCP server is an essential component for your toolkit.

**Nikolas de Hor**
Goiânia, GO, Brazil

---
### Contributing
The project is in an expansion phase. We plan to support direct invoice issuance (via A1 certificates) and integration with over 50 municipal portals for NFSe. Feel free to open issues or submit pull requests on the official repository.

[Access MCP Fiscal Brasil on GitHub](https://github.com/DeHor-Labs/mcp-fiscal-brasil)
