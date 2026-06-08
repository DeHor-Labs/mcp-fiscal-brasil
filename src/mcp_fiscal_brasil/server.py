"""
Servidor MCP Fiscal Brasil.

Registra todas as ferramentas fiscais e expõe via protocolo MCP (Model Context Protocol).
"""

import logging
from typing import Any

from fastmcp import FastMCP

from . import __version__
from .agentic import (
    analyze_cnpj_compliance,
    compare_tax_regimes,
    consultar_empresas_lote,
    risk_score_supplier,
    summarize_sped,
    validate_nfe_full,
)
from .certidoes.tools import consultar_certidao_federal, consultar_certidao_fgts

# Importa todas as ferramentas dos modulos fiscais
from .cnpj.tools import consultar_cnpj, listar_cnpjs_por_nome
from .cpf.tools import validar_cpf_tool
from .esocial.tools import listar_eventos_esocial, validar_evento_esocial
from .nfe.tools import consultar_nfe, consultar_status_sefaz, validar_chave_nfe
from .nfse.tools import consultar_nfse
from .shared.validators import validate_cnpj
from .simples.tools import consultar_simples_nacional
from .sped.tools import analisar_sped, listar_registros_sped

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

MAX_CNPJS_POR_LOTE = 50


def _normalizar_e_validar_cnpjs(cnpjs: list[str]) -> list[str]:
    if len(cnpjs) > MAX_CNPJS_POR_LOTE:
        raise ValueError(
            f"Tamanho do lote inválido: recebeu {len(cnpjs)} CNPJs, máximo permitido é "
            f"{MAX_CNPJS_POR_LOTE}."
        )

    invalidos: list[str] = []
    normalizados: list[str] = []

    for cnpj in cnpjs:
        if not validate_cnpj(cnpj):
            invalidos.append(cnpj)
            continue
        normalizados.append("".join(caractere for caractere in cnpj if caractere.isdigit()))

    if invalidos:
        raise ValueError(
            "CNPJ(s) inválido(s) no lote. "
            f"Verifique o formato e o dígito verificador: {', '.join(invalidos)}"
        )

    return normalizados


app = FastMCP(
    name="MCP Fiscal Brasil",
    version=__version__,
    instructions=(
        "Servidor MCP para integrar IAs com o sistema fiscal brasileiro. "
        "Consulte CNPJ, NFe, NFSe, SPED, eSocial e certidões via linguagem natural. "
        "Dados obtidos de fontes públicas: BrasilAPI, ReceitaWS, SEFAZ."
    ),
)

# ---------------------------------------------------------------------------
# CNPJ
# ---------------------------------------------------------------------------


@app.tool(
    name="consultar_cnpj",
    description=(
        "Consulta os dados cadastrais completos de uma empresa pelo CNPJ. "
        "Retorna razão social, endereço, atividades econômicas (CNAE), "
        "sócios (QSA), situação cadastral e porte da empresa. "
        "Aceita CNPJ com ou sem formatação (pontos, barra, traço)."
    ),
)
async def tool_consultar_cnpj(cnpj: str) -> dict[str, Any]:
    """Consulta o cadastro completo de uma empresa brasileira pelo CNPJ.

    Recupera os dados publicos da pessoa juridica na Receita Federal (via BrasilAPI/ReceitaWS):
    razao social, nome fantasia, endereco, situacao cadastral, natureza juridica, porte,
    capital social, CNAE principal e secundarias e quadro de socios e administradores (QSA).
    Util para identificar empresas, validar fornecedores/clientes e preencher dados fiscais.

    Args:
        cnpj: Numero do CNPJ com 14 digitos, com ou sem formatacao
            (ex.: "11.222.333/0001-81" ou "11222333000181").

    Returns:
        dict com os dados cadastrais completos da empresa.
    """
    resultado = await consultar_cnpj(cnpj)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="listar_cnpjs_por_nome",
    description=(
        "Busca empresas pelo nome ou razão social. "
        "Nota: esta funcionalidade tem disponibilidade limitada em APIs públicas."
    ),
)
async def tool_listar_cnpjs_por_nome(nome: str, uf: str | None = None) -> list[dict[str, str]]:
    """Busca empresas pelo nome empresarial ou razao social.

    A busca textual por nome de empresa nao e coberta por APIs publicas gratuitas, entao
    esta ferramenta retorna um aviso orientando o uso de consultar_cnpj com o CNPJ exato.

    Args:
        nome: Nome empresarial ou parte da razao social a procurar.
        uf: Sigla do estado para restringir a busca (ex.: "SP", "MG"). Opcional.

    Returns:
        list de dicts; atualmente contem um aviso de funcionalidade limitada.
    """
    return await listar_cnpjs_por_nome(nome, uf)


# ---------------------------------------------------------------------------
# CPF
# ---------------------------------------------------------------------------


@app.tool(
    name="validar_cpf",
    description=(
        "Valida o dígito verificador de um CPF brasileiro. "
        "Verificação matemática offline - não consulta APIs externas. "
        "A Receita Federal não disponibiliza API pública para dados de CPF."
    ),
)
async def tool_validar_cpf(cpf: str) -> dict[str, Any]:
    """Valida o digito verificador de um CPF brasileiro (offline, modulo 11).

    Confere apenas a estrutura do numero (11 digitos, nao-repetidos, digitos verificadores).
    Nao consulta a Receita Federal nem confirma a existencia ou a situacao do titular.

    Args:
        cpf: Numero do CPF com 11 digitos, com ou sem formatacao
            (ex.: "123.456.789-09" ou "12345678909").

    Returns:
        dict indicando se o CPF e matematicamente valido, com versao formatada e motivo da reprovacao.
    """
    resultado = await validar_cpf_tool(cpf)
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# NFe
# ---------------------------------------------------------------------------


@app.tool(
    name="consultar_nfe",
    description=(
        "Consulta os dados de uma Nota Fiscal Eletrônica (NFe) pela chave de acesso de 44 dígitos. "
        "A chave pode ser encontrada no DANFE (documento impresso da nota). "
        "Retorna emitente, destinatário, itens, valores e protocolo de autorização."
    ),
)
async def tool_consultar_nfe(chave_acesso: str) -> dict[str, Any]:
    """Consulta uma NF-e (Nota Fiscal Eletronica) pela chave de acesso de 44 digitos.

    Recupera emitente, destinatario, itens, valores e o protocolo de autorizacao da SEFAZ.
    Use para conferencia, escrituracao fiscal/contabil ou auditoria de notas ja emitidas.

    Args:
        chave_acesso: Chave de acesso da NF-e com 44 digitos (aceita com ou sem espacos).

    Returns:
        dict com emitente, destinatario, itens, totais e protocolo da nota.
    """
    resultado = await consultar_nfe(chave_acesso)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="validar_chave_nfe",
    description=(
        "Valida o formato e o dígito verificador de uma chave de acesso de NFe. "
        "Não consulta APIs - apenas verifica o cálculo matemático (módulo 11). "
        "Também extrai informações da chave: UF, data de emissão, CNPJ emitente e número da nota."
    ),
)
async def tool_validar_chave_nfe(chave_acesso: str) -> dict[str, Any]:
    """Valida o formato e o digito verificador de uma chave de acesso de NF-e (offline, modulo 11).

    Nao consulta a SEFAZ; apenas confere o calculo e decodifica os metadados da chave
    (UF, ano/mes de emissao, CNPJ emitente, modelo, serie e numero da nota).

    Args:
        chave_acesso: Chave de acesso com 44 digitos (aceita com ou sem espacos).

    Returns:
        dict com "valido", "chave_formatada" e, se valida, "uf", "ano_mes_emissao",
        "cnpj_emitente", "modelo", "serie" e "numero".
    """
    return await validar_chave_nfe(chave_acesso)


@app.tool(
    name="consultar_status_sefaz",
    description=(
        "Consulta o status atual do serviço SEFAZ de um estado brasileiro. "
        "Verifica se o webservice da SEFAZ para emissão de NFe está operacional. "
        "Útil para diagnosticar falhas de transmissão de notas fiscais."
    ),
)
async def tool_consultar_status_sefaz(uf: str) -> dict[str, Any]:
    """Consulta o status do servico de autorizacao de NF-e da SEFAZ de uma UF.

    Indica se o webservice da SEFAZ do estado esta operacional, util para diagnosticar
    falhas na transmissao de notas fiscais.

    Args:
        uf: Sigla do estado com 2 letras (ex.: "SP", "MG", "RJ"). Validada contra as UFs do Brasil.

    Returns:
        dict com o status atual do servico e a descricao correspondente.
    """
    resultado = await consultar_status_sefaz(uf)
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# NFSe
# ---------------------------------------------------------------------------


@app.tool(
    name="consultar_nfse",
    description=(
        "Consulta dados de uma NFSe (Nota Fiscal de Serviço Eletrônica). "
        "ATENÇÃO: NFSe não possui padrão nacional - cada município tem seu próprio sistema. "
        "Esta ferramenta orienta sobre como acessar o portal correto do município."
    ),
)
async def tool_consultar_nfse(
    numero: str,
    municipio: str,
    uf: str,
    cnpj_prestador: str | None = None,
) -> dict[str, str]:
    """Orienta a consulta de uma NFS-e (Nota Fiscal de Servicos eletronica) por municipio.

    A NFS-e e municipal e nao tem padrao nacional unico, entao esta ferramenta retorna o portal
    da prefeitura, o tipo de sistema (ABRASF, ISS.net etc.) e alternativas de integracao, em vez
    de buscar os dados da nota diretamente.

    Args:
        numero: Numero da NFS-e.
        municipio: Nome do municipio emissor (ex.: "Sao Paulo", "Belo Horizonte").
        uf: Sigla do estado com 2 letras (ex.: "SP", "MG").
        cnpj_prestador: CNPJ do prestador de servico. Opcional.

    Returns:
        dict com orientacoes de consulta, portal e sistema do municipio e alternativas de automacao.
    """
    return await consultar_nfse(numero, municipio, uf, cnpj_prestador)


# ---------------------------------------------------------------------------
# Simples Nacional
# ---------------------------------------------------------------------------


@app.tool(
    name="consultar_simples_nacional",
    description=(
        "Consulta se uma empresa é optante do Simples Nacional ou MEI. "
        "Retorna situação atual, datas de opção e exclusão do regime simplificado."
    ),
)
async def tool_consultar_simples_nacional(cnpj: str) -> dict[str, Any]:
    """Consulta a situacao de uma empresa no Simples Nacional e no MEI pelo CNPJ.

    Retorna se e optante do Simples Nacional e/ou MEI, com datas de opcao e exclusao.
    Util para definir o regime tributario antes de calcular impostos ou tributar notas fiscais.

    Args:
        cnpj: Numero do CNPJ com 14 digitos, com ou sem formatacao.

    Returns:
        dict com a situacao no Simples Nacional e no MEI e respectivas datas.
    """
    resultado = await consultar_simples_nacional(cnpj)
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# SPED
# ---------------------------------------------------------------------------


@app.tool(
    name="analisar_sped",
    description=(
        "Analisa um arquivo SPED (EFD-ICMS/IPI, EFD-Contribuições, ECD ou ECF) "
        "e extrai informações sobre período, empresa, tipos de registros e possíveis erros. "
        "Recebe o conteúdo do arquivo como texto (formato pipe-delimitado)."
    ),
)
async def tool_analisar_sped(conteudo: str, nome_arquivo: str | None = None) -> dict[str, Any]:
    """Analisa um arquivo SPED e extrai periodo, empresa, contagem de registros e erros.

    Identifica o tipo de escrituracao pelo registro 0000 (EFD-ICMS/IPI, EFD-Contribuicoes, ECD, ECF)
    e devolve um resumo estruturado, com avisos e erros de integridade basica.

    Args:
        conteudo: Texto do arquivo SPED (layout delimitado por pipe "|"), nao um caminho.
        nome_arquivo: Nome do arquivo, apenas informativo. Opcional.

    Returns:
        dict com tipo de SPED, dados de abertura, periodo, contagem de registros, avisos e erros.
    """
    resultado = await analisar_sped(conteudo, nome_arquivo)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="listar_registros_sped",
    description=(
        "Lista todas as ocorrências de um tipo de registro específico em um arquivo SPED. "
        "Exemplo: buscar todos os registros C100 (documentos fiscais) ou E110 (apuração ICMS)."
    ),
)
async def tool_listar_registros_sped(conteudo: str, tipo_registro: str) -> list[dict[str, str]]:
    """Lista todas as ocorrencias de um tipo de registro dentro de um arquivo SPED.

    Para cada linha cujo codigo inicial coincide com tipo_registro, retorna o codigo,
    os campos concatenados por pipe e a linha bruta.

    Args:
        conteudo: Texto do arquivo SPED (layout delimitado por pipe "|").
        tipo_registro: Codigo do registro a buscar (ex.: "C100", "E110", "0150"). Case-insensitive.

    Returns:
        list de dicts com "registro", "campos" e "raw" para cada ocorrencia encontrada.
    """
    return await listar_registros_sped(conteudo, tipo_registro)


# ---------------------------------------------------------------------------
# eSocial
# ---------------------------------------------------------------------------


@app.tool(
    name="listar_eventos_esocial",
    description=(
        "Lista os eventos do eSocial com nome, grupo e descrição. "
        "Pode filtrar por grupo: 'Tabelas', 'Não Periodicos', 'Periodicos' ou 'Exclusao'."
    ),
)
async def tool_listar_eventos_esocial(grupo: str | None = None) -> list[dict[str, Any]]:
    """Lista os eventos do eSocial (layouts da serie S-) do catalogo interno.

    Retorna codigo, nome, grupo e descricao de cada evento, opcionalmente filtrados por grupo.

    Args:
        grupo: Filtro por grupo, com correspondencia parcial e sem distincao de maiusculas
            (ex.: "Tabelas", "Nao Periodicos", "Periodicos", "Exclusao", "Totalizadores").
            Se None, retorna todos os eventos ordenados por codigo.

    Returns:
        list de dicts com codigo, nome, grupo e descricao de cada evento.
    """
    eventos = await listar_eventos_esocial(grupo)
    return [e.model_dump() for e in eventos]


@app.tool(
    name="validar_evento_esocial",
    description=(
        "Realiza validação básica de estrutura de um XML de evento eSocial. "
        "Verifica presença do elemento raiz correto, código do evento e versão do leiaute."
    ),
)
async def tool_validar_evento_esocial(xml_conteudo: str) -> dict[str, Any]:
    """Valida a estrutura basica de um XML de evento do eSocial.

    Verifica o elemento raiz, identifica o codigo do evento (elemento "evt...") e extrai a
    versao do leiaute. Nao substitui a validacao contra o schema XSD oficial.

    Args:
        xml_conteudo: Conteudo (texto) do XML do evento eSocial.

    Returns:
        dict com o evento detectado, a versao, o resultado da validacao e listas de erros e avisos.
    """
    resultado = await validar_evento_esocial(xml_conteudo)
    return resultado.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# Certidoes
# ---------------------------------------------------------------------------


@app.tool(
    name="consultar_certidao_federal",
    description=(
        "Orienta sobre como consultar a Certidão Negativa de Débitos (CND) "
        "da Receita Federal e PGFN para CNPJ ou CPF. "
        "Fornece URLs de emissão e verificação e alternativas para automação."
    ),
)
async def tool_consultar_certidao_federal(cnpj_cpf: str) -> dict[str, str]:
    """Orienta a obtencao da Certidao Negativa de Debitos federais (CND da RFB/PGFN) por CPF ou CNPJ.

    Detecta o tipo de documento, valida o numero e retorna as URLs oficiais de emissao e verificacao,
    o acesso ao e-CAC e alternativas de automacao. Nao emite a certidao (nao ha API publica).

    Args:
        cnpj_cpf: CPF (11 digitos) ou CNPJ (14 digitos), com ou sem formatacao.

    Returns:
        dict com tipo de documento, motivo da consulta manual, URLs de emissao/verificacao e alternativas.
    """
    return await consultar_certidao_federal(cnpj_cpf)


@app.tool(
    name="consultar_certidao_fgts",
    description=(
        "Orienta sobre como consultar a Certidão de Regularidade do FGTS (CRF) "
        "para um CNPJ. Fornece URL do portal da Caixa e alternativas para automação."
    ),
)
async def tool_consultar_certidao_fgts(cnpj: str) -> dict[str, str]:
    """Orienta a obtencao do Certificado de Regularidade do FGTS (CRF) por CNPJ.

    Valida o CNPJ e retorna a URL de consulta no portal da Caixa, o Conectividade Social e
    orientacoes de automacao. Nao emite o certificado (nao ha API publica aberta).

    Args:
        cnpj: CNPJ do empregador com 14 digitos, com ou sem formatacao.

    Returns:
        dict com orgao, motivo da consulta manual, URLs de consulta e orientacoes de automacao.
    """
    return await consultar_certidao_fgts(cnpj)


# ---------------------------------------------------------------------------
# Agentic (tools de alto nivel orientadas a IA)
# ---------------------------------------------------------------------------


@app.tool(
    name="analyze_cnpj_compliance",
    description=(
        "Analise consolidada de compliance fiscal de um CNPJ. "
        "Combina dados cadastrais (Receita), regime tributário (Simples Nacional), "
        "status MEI e CNAE em um relatório unico com score 0-100, risco classificado "
        "(baixo/medio/alto/critico) e achados acionaveis. "
        "Use para decisão de contratar/recusar/investigar uma empresa em uma chamada."
    ),
)
async def tool_analyze_cnpj_compliance(cnpj: str) -> dict[str, Any]:
    """Analise consolidada de compliance fiscal."""
    resultado = await analyze_cnpj_compliance(cnpj)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="compare_tax_regimes",
    description=(
        "Compara regimes tributarios brasileiros (MEI, Simples Nacional, Lucro Presumido, "
        "Lucro Real) para um cenário de faturamento e setor. Retorna estimativa de alíquota "
        "efetiva, imposto anual e melhor opção. Util para planejamento tributário rápido. "
        "Setor: comércio, serviços ou indústria. Folha opcional impacta Fator R no Simples."
    ),
)
async def tool_compare_tax_regimes(
    faturamento_anual: float,
    setor: str,
    folha_pagamento_anual: float | None = None,
) -> dict[str, Any]:
    """Compara regimes tributarios para um cenário."""
    if setor not in ("comércio", "serviços", "indústria"):
        raise ValueError("setor deve ser: comércio, serviços ou indústria")
    resultado = compare_tax_regimes(
        faturamento_anual=faturamento_anual,
        setor=setor,  # type: ignore[arg-type]
        folha_pagamento_anual=folha_pagamento_anual,
    )
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="risk_score_supplier",
    description=(
        "Calcula score de risco (0-100) para due diligence de fornecedor. "
        "Combina ComplianceReport com ajustes conservadores para contratacao. "
        "Retorna recomendacao binaria (aprovar/aprovar_com_ressalvas/investigar/recusar). "
        "Opcao criterios_estritos=true reduz score em 10 para politicas anti-corrupcao."
    ),
)
async def tool_risk_score_supplier(cnpj: str, criterios_estritos: bool = False) -> dict[str, Any]:
    """Score de risco para due diligence de fornecedor."""
    resultado = await risk_score_supplier(cnpj, criterios_estritos)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="consultar_empresas_lote",
    description=(
        "Consulta em lote múltiplos CNPJs e devolve, em uma única chamada, "
        "o resumo de compliance + score de risco de fornecedor para cada empresa. "
        "Útil para triagem rápida de carteira de fornecedores, com erros por CNPJ retornados "
        "se algum dado falhar."
    ),
)
async def tool_consultar_empresas_lote(
    cnpjs: list[str],
    criterios_estritos: bool = False,
) -> dict[str, Any]:
    """Consulta em lote consolidada de compliance e risco de fornecedores."""
    cnpjs_normalizados = _normalizar_e_validar_cnpjs(cnpjs)
    resultado = await consultar_empresas_lote(
        cnpjs_normalizados,
        criterios_estritos=criterios_estritos,
    )
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="validate_nfe_full",
    description=(
        "Validacao consolidada de uma NFe a partir do XML: parse estrutural, validação "
        "do digito verificador da chave, verificacao de situacao do CNPJ emissor. "
        "Recebe caminho de arquivo XML local. Retorna relatório com chave, validade, "
        "issues e resumo."
    ),
)
async def tool_validate_nfe_full(xml_path: str) -> dict[str, Any]:
    """Validacao consolidada de NFe."""
    resultado = await validate_nfe_full(xml_path)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="summarize_sped",
    description=(
        "Sumarizacao executiva de um arquivo SPED (Fiscal, Contribuicoes, ECF ou ECD). "
        "Identifica tipo, extrai período, empresa, total de registros, blocos e produz "
        "resumo em pt-BR. Recebe caminho de arquivo .txt local."
    ),
)
async def tool_summarize_sped(file_path: str) -> dict[str, Any]:
    """Sumarizacao executiva de arquivo SPED."""
    resultado = await summarize_sped(file_path)
    return resultado.model_dump(mode="json", exclude_none=True)


def main() -> None:
    """Inicia o servidor MCP.

    Modo de transporte configurável via argumento --transport ou variável de ambiente
    FASTMCP_TRANSPORT. Valores aceitos: stdio (padrão), sse, http, streamable-http.

    Para HTTP/SSE, a porta é configurada via variável PORT (padrão: 8000).
    """
    import argparse
    import os

    parser = argparse.ArgumentParser(description="MCP Fiscal Brasil")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http", "streamable-http"],
        default=os.environ.get("FASTMCP_TRANSPORT", "stdio"),
        help="Protocolo de transporte (padrão: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Porta HTTP/SSE (padrão: 8000, ou valor da variável PORT)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "0.0.0.0"),
        help="Host para HTTP/SSE (padrão: 0.0.0.0)",
    )
    args = parser.parse_args()

    logger.info("Iniciando MCP Fiscal Brasil v%s (transport=%s)", __version__, args.transport)

    if args.transport == "stdio":
        app.run(transport="stdio")
    else:
        app.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
