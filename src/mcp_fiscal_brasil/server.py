"""
Servidor MCP Fiscal Brasil.

Registra todas as ferramentas fiscais e expõe via protocolo MCP (Model Context Protocol).
"""

import logging
import unicodedata
from typing import Any, Literal

from fastmcp import FastMCP

from . import __version__
from .agentic import (
    analyze_cnpj_compliance,
    compare_tax_regimes,
    consultar_empresas_lote,
    risk_score_supplier,
    simular_transicao_reforma_tributaria,
    summarize_sped,
    validate_nfe_full,
)
from .bcb import _tools as bcb_tools
from .cep import _tools as cep_tools
from .certidoes.tools import consultar_certidao_federal, consultar_certidao_fgts
from .cnae import _tools as cnae_tools

# Importa todas as ferramentas dos modulos fiscais
from .cnpj.tools import consultar_cnpj, listar_cnpjs_por_nome
from .cpf.tools import validar_cpf_tool
from .empresa import _tools as empresa_tools
from .esocial.tools import listar_eventos_esocial, validar_evento_esocial
from .ibge import _tools as ibge_tools
from .mei import _tools as mei_tools
from .nfe.assinatura import AssinaturaResult, validar_assinatura_nfe
from .nfe.danfe import DanfeResult, gerar_danfe
from .nfe.distribuicao import (
    DistribuicaoResult,
    ManifestacaoResult,
    baixar_nfe_distribuicao,
    manifestar_nfe,
)
from .nfe.documento import parse_nfe_documento
from .nfe.tools import consultar_nfe, consultar_status_sefaz, validar_chave_nfe
from .nfse.tools import consultar_nfse
from .shared.validators import normalizar_cnpj, validate_cnpj_qualquer
from .simples.tools import consultar_simples_nacional
from .sped.tools import analisar_sped, listar_registros_sped
from .tabelas import _tools as tabelas_tools

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
        if not validate_cnpj_qualquer(cnpj):
            invalidos.append(cnpj)
            continue
        normalizados.append(normalizar_cnpj(cnpj))

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
        "Busca empresas pelo nome empresarial ou razão social. "
        "Quando usar: quando só se conhece o nome da empresa e não o CNPJ; "
        "não usar quando o CNPJ já é conhecido (prefira consultar_cnpj). "
        "Comportamento: APIs públicas gratuitas não cobrem busca textual por nome; "
        "a ferramenta retorna orientação para obter o CNPJ via fontes adequadas. "
        "Parâmetros: nome (obrigatório), uf (sigla do estado, opcional)."
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


@app.tool(
    name="parse_nfe_xml",
    description=(
        "Parseia o XML completo de uma NF-e ou NFC-e e retorna os dados estruturados. "
        "Aceita XML com ou sem o involucro <nfeProc> e com ou sem namespace do portal fiscal. "
        "Util para extrair emitente, destinatario, itens, totais e protocolo a partir do XML bruto."
    ),
)
async def tool_parse_nfe_xml(xml_content: str) -> dict[str, Any]:
    """Parseia o XML completo de uma NF-e ou NFC-e e retorna os dados estruturados.

    Extrai automaticamente a chave de acesso do atributo Id do elemento <infNFe>.
    Aceita XMLs com ou sem involucro de protocolo <nfeProc>, com ou sem namespace
    do portal fiscal (http://www.portalfiscal.inf.br/nfe).

    Args:
        xml_content: XML completo da NF-e ou NFC-e como string. Pode conter
                     o involucro <nfeProc> ou ser a NF-e nua. Aceita XML com
                     ou sem namespace do portal fiscal.

    Returns:
        dict com os dados do documento: chave_acesso, modelo, emitente, destinatario,
        itens, totais, protocolo_autorizacao e demais campos da NFeResponse.

    Raises:
        DocumentoParseError: Se o XML for invalido ou a chave nao tiver 44 digitos.
        XMLParseError: Se o XML estiver malformado.
    """
    resultado = parse_nfe_documento(xml_content)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="gerar_danfe",
    description=(
        "Gera o DANFE (Documento Auxiliar da Nota Fiscal Eletronica) em PDF a partir do XML de NF-e. "
        "Suporta apenas NF-e modelo 55. O PDF e retornado em base64. "
        "ATENCAO: o XML deve conter o namespace do portal fiscal "
        "(xmlns='http://www.portalfiscal.inf.br/nfe'). "
        "Nao e necessario certificado digital - funciona apenas com o XML."
    ),
)
async def tool_gerar_danfe(xml_content: str) -> dict[str, Any]:
    """Gera o DANFE em PDF a partir do XML de uma NF-e (modelo 55).

    Utiliza a lib brazilfiscalreport para gerar o DANFE A4 no formato retrato.
    O PDF e retornado como base64 no campo pdf_base64 do resultado.

    NAMESPACE OBRIGATORIO: o XML deve conter o namespace do portal fiscal
    (http://www.portalfiscal.inf.br/nfe). Modelo 65 (NFC-e) nao e suportado
    na versao atual.

    SEGURANCA: o XML e validado contra XXE (billion-laughs, entidades externas)
    antes de ser entregue a lib de geracao do PDF.

    Args:
        xml_content: XML completo da NF-e como string. Deve conter o namespace
                     do portal fiscal. Aceita XML com ou sem involucro <nfeProc>.

    Returns:
        dict com pdf_base64 (PDF em base64), modelo, nome_arquivo, chave_acesso,
        numero e serie.
    """
    resultado: DanfeResult = gerar_danfe(xml_content)
    return resultado.model_dump(mode="json", exclude_none=True)


@app.tool(
    name="validar_assinatura_nfe",
    description=(
        "Valida a assinatura digital XMLDSig de uma NF-e. "
        "Verifica a integridade do DigestValue e a assinatura criptografica do certificado. "
        "Extrai dados do certificado assinante: titular, CNPJ/CPF, validade e autoridade certificadora. "
        "Opcional: informe um CA bundle PEM para validar a cadeia de confianca ICP-Brasil."
    ),
)
async def tool_validar_assinatura_nfe(
    xml_content: str,
    ca_bundle: str | None = None,
) -> dict[str, Any]:
    """Valida a assinatura digital XMLDSig de uma NF-e.

    Verifica a integridade (DigestValue) e a assinatura criptografica do
    elemento Signature presente em infNFe. Extrai dados do certificado assinante.

    Sem ca_bundle: valida apenas a assinatura criptografica e integridade do digest
    usando o certificado embutido no proprio XML. Nao verifica se o certificado
    e confiavel (sem cadeia ICP-Brasil).

    Com ca_bundle (PEM): valida a assinatura E a cadeia de confianca ICP-Brasil,
    garantindo que o certificado foi emitido por uma AC credenciada.

    Args:
        xml_content: Conteudo XML da NF-e como string. Validado contra XXE (parse_xml).
        ca_bundle: Opcional. Conteudo PEM (nao o caminho, mas o PEM em si) com a
                   cadeia ICP-Brasil para validar o emissor do certificado.

    Returns:
        dict com assinatura_valida (bool), motivo (se invalida), titular (CN),
        cnpj_cpf, validade_inicio, validade_fim e ac_emissora.
    """
    resultado: AssinaturaResult = validar_assinatura_nfe(
        xml_content,
        ca_bundle=ca_bundle.encode() if ca_bundle else None,
    )
    return {
        "assinatura_valida": resultado.assinatura_valida,
        "motivo": resultado.motivo,
        "titular": resultado.titular,
        "cnpj_cpf": resultado.cnpj_cpf,
        "validade_inicio": resultado.validade_inicio.isoformat()
        if resultado.validade_inicio
        else None,
        "validade_fim": resultado.validade_fim.isoformat() if resultado.validade_fim else None,
        "ac_emissora": resultado.ac_emissora,
    }


@app.tool(
    name="baixar_nfe_distribuicao",
    description=(
        "Baixa documentos fiscais via NFeDistribuicaoDFe (SEFAZ) usando certificado A1 local. "
        "REQUER certificado digital A1 (.pfx/.p12) do proprio usuario instalado localmente. "
        "O certificado NUNCA e enviado a nenhum servidor - a autenticacao e feita localmente via mTLS. "
        "Suporta busca incremental (distNSU), por NSU especifico (consNSU) ou por chave (consChNFe). "
        "A Ciencia da Operacao (210200) e prerequisito para obter o XML completo (procNFe)."
    ),
)
async def tool_baixar_nfe_distribuicao(
    caminho_certificado: str,
    senha: str,
    cnpj_cpf: str,
    uf: str,
    modo: str = "distNSU",
    ultimo_nsu: str = "0",
    nsu: str | None = None,
    chave: str | None = None,
    ambiente: str = "producao",
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Baixa documentos fiscais via NFeDistribuicaoDFe com mTLS usando certificado A1 local.

    CERTIFICADO LOCAL (opt-in): requer o caminho absoluto para o arquivo .pfx/.p12
    e a senha. O certificado NUNCA e enviado a qualquer servidor externo. A autenticacao
    mTLS e feita diretamente entre o cliente e a SEFAZ.

    A Ciencia da Operacao (evento 210200) e pre-requisito para a SEFAZ liberar o
    XML completo (procNFe) ao destinatario. Sem ela, apenas o resNFe (resumo) fica
    disponivel. Use manifestar_nfe() apos obter o resNFe.

    Args:
        caminho_certificado: Caminho absoluto para o arquivo .pfx ou .p12.
        senha: Senha do certificado. Nunca logada ou incluida em excecoes.
        cnpj_cpf: CNPJ (14 dig) ou CPF (11 dig) do autor da consulta.
        uf: Sigla da UF do autor (ex: "SP") ou codigo IBGE (ex: "35").
        modo: "distNSU" (incremental), "consNSU" (NSU especifico) ou
              "consChNFe" (por chave de acesso de 44 digitos).
        ultimo_nsu: Ultimo NSU recebido para modo distNSU. Default "0" busca todos.
        nsu: NSU especifico para modo consNSU.
        chave: Chave de acesso de 44 digitos para modo consChNFe.
        ambiente: "producao" ou "homologacao".
        timeout: Timeout HTTP em segundos (default 30.0).

    Returns:
        dict com ultimo_nsu, max_nsu e documentos (lista com nsu, tipo, schema,
        chave e resumo de cada documento retornado).
    """
    resultado: DistribuicaoResult = await baixar_nfe_distribuicao(
        caminho_certificado=caminho_certificado,
        senha=senha,
        cnpj_cpf=cnpj_cpf,
        uf=uf,
        modo=modo,  # type: ignore[arg-type]
        ultimo_nsu=ultimo_nsu,
        nsu=nsu,
        chave=chave,
        ambiente=ambiente,  # type: ignore[arg-type]
        timeout=timeout,
    )
    # Serializa manualmente pois DistribuicaoResult e dataclass frozen com nested dataclasses
    docs = []
    for doc in resultado.documentos:
        docs.append(
            {
                "nsu": doc.nsu,
                "tipo": doc.tipo,
                "schema": doc.schema,
                "chave": doc.chave,
                "resumo": doc.resumo,
                "dados_completos": (
                    doc.dados_completos.model_dump(mode="json", exclude_none=True)
                    if doc.dados_completos is not None
                    else None
                ),
            }
        )
    return {
        "ultimo_nsu": resultado.ultimo_nsu,
        "max_nsu": resultado.max_nsu,
        "documentos": docs,
    }


@app.tool(
    name="manifestar_nfe",
    description=(
        "Manifesta o destinatario em uma NF-e via NFeRecepcaoEvento. "
        "REQUER certificado digital A1 (.pfx/.p12) do proprio usuario instalado localmente. "
        "O certificado NUNCA e enviado a nenhum servidor - a assinatura e feita localmente. "
        "Eventos: 210200 (Ciencia), 210210 (Confirmacao), 210220 (Desconhecimento), "
        "210240 (Operacao nao Realizada, requer justificativa). "
        "A Ciencia (210200) e prerequisito obrigatorio para obter o XML completo da NF-e."
    ),
)
async def tool_manifestar_nfe(
    chave: str,
    tipo_evento: str,
    caminho_certificado: str,
    senha: str,
    cnpj_cpf: str,
    uf: str = "91",
    numero_sequencia: int = 1,
    justificativa: str | None = None,
    ambiente: str = "producao",
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Manifesta o destinatario em uma NF-e via NFeRecepcaoEvento.

    CERTIFICADO LOCAL (opt-in): requer o caminho absoluto para o arquivo .pfx/.p12
    e a senha. O certificado NUNCA e enviado a qualquer servidor. A assinatura XMLDSig
    do evento e feita localmente e o XML assinado e enviado diretamente a SEFAZ.

    Eventos disponiveis:
    - 210200: Ciencia da Operacao (pre-requisito para obter procNFe)
    - 210210: Confirmacao da Operacao
    - 210220: Desconhecimento da Operacao
    - 210240: Operacao nao Realizada (justificativa OBRIGATORIA, minimo 15 caracteres)

    Args:
        chave: Chave de acesso de 44 digitos da NF-e.
        tipo_evento: Codigo do evento ("210200", "210210", "210220" ou "210240").
        caminho_certificado: Caminho absoluto para o arquivo .pfx/.p12.
        senha: Senha do certificado A1. Nunca logada ou incluida em excecoes.
        cnpj_cpf: CNPJ (14 dig) ou CPF (11 dig) do destinatario.
        uf: UF do autor. Default "91" = AN (Ambiente Nacional) para manifestacao.
        numero_sequencia: Numero sequencial do evento para esta chave (1 a 20).
        justificativa: Obrigatoria para evento 210240 (minimo 15 caracteres).
        ambiente: "producao" ou "homologacao".
        timeout: Timeout HTTP em segundos (default 30.0).

    Returns:
        dict com sucesso (bool), chave, tipo_evento, numero_protocolo,
        codigo_retorno e motivo retornados pela SEFAZ.
    """
    resultado: ManifestacaoResult = await manifestar_nfe(
        chave=chave,
        tipo_evento=tipo_evento,
        caminho_certificado=caminho_certificado,
        senha=senha,
        cnpj_cpf=cnpj_cpf,
        uf=uf,
        numero_sequencia=numero_sequencia,
        justificativa=justificativa,
        ambiente=ambiente,  # type: ignore[arg-type]
        timeout=timeout,
    )
    return {
        "sucesso": resultado.sucesso,
        "chave": resultado.chave,
        "tipo_evento": resultado.tipo_evento,
        "numero_protocolo": resultado.numero_protocolo,
        "codigo_retorno": resultado.codigo_retorno,
        "motivo": resultado.motivo,
    }


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
    """Analise consolidada de compliance fiscal de um CNPJ.

    Combina dados da Receita Federal, Simples Nacional e CNAE para produzir
    um relatorio com score 0-100, classificacao de risco e achados acionaveis.

    Args:
        cnpj: Numero do CNPJ com 14 digitos, com ou sem formatacao.

    Returns:
        dict com score, risco, situacao, regime, cnae e lista de achados.
    """
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


# ---------------------------------------------------------------------------
# Helpers de normalizacao de entrada para o simulador de reforma tributaria
# ---------------------------------------------------------------------------


def _remover_acentos(texto: str) -> str:
    """Remove diacriticos de uma string (ex.: 'comércio' -> 'comercio')."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


# Mapeamentos de normalizacao: chave sem acento em casefold -> valor canonico
_mapa_setor: dict[str, Literal["comércio", "serviços", "indústria"]] = {
    "comercio": "comércio",
    "servicos": "serviços",
    "industria": "indústria",
}

_mapa_regime: dict[str, Literal["Simples Nacional", "Lucro Presumido", "Lucro Real"]] = {
    "simples nacional": "Simples Nacional",
    "simples": "Simples Nacional",
    "lucro presumido": "Lucro Presumido",
    "presumido": "Lucro Presumido",
    "lucro real": "Lucro Real",
    "real": "Lucro Real",
}


def _normalizar_setor(setor: str) -> Literal["comércio", "serviços", "indústria"]:
    """Normaliza a entrada de setor aceitando variantes sem acento e em qualquer caixa.

    Exemplos aceitos: 'comercio', 'COMERCIO', 'Comércio' -> 'comércio'.
    """
    chave = _remover_acentos(setor.strip().casefold())
    canonico = _mapa_setor.get(chave)
    if canonico is None:
        opcoes = ", ".join(f'"{v}"' for v in ("comércio", "serviços", "indústria"))
        raise ValueError(f'Setor "{setor}" nao reconhecido. Use um dos valores validos: {opcoes}.')
    return canonico


def _normalizar_regime(
    regime: str,
) -> Literal["Simples Nacional", "Lucro Presumido", "Lucro Real"]:
    """Normaliza a entrada de regime tributario aceitando variantes sem acento e em qualquer caixa.

    Exemplos aceitos: 'simples nacional', 'SIMPLES NACIONAL', 'simples' -> 'Simples Nacional'.
    """
    chave = _remover_acentos(regime.strip().casefold())
    canonico = _mapa_regime.get(chave)
    if canonico is None:
        opcoes = ", ".join(f'"{v}"' for v in ("Simples Nacional", "Lucro Presumido", "Lucro Real"))
        raise ValueError(
            f'Regime "{regime}" nao reconhecido. Use um dos valores validos: {opcoes}.'
        )
    return canonico


@app.tool(
    name="simular_transicao_reforma_tributaria",
    description=(
        "Simula o impacto da Reforma Tributaria (LC 214/2025) ano a ano de 2026 a 2033. "
        "Compara a carga do regime antigo (PIS/COFINS + ICMS ou ISS) com a do regime novo "
        "(CBS + IBS), mostrando o blend da transicao conforme o cronograma legal. "
        "Setores: comercio, servicos ou industria. "
        "Regimes: Simples Nacional, Lucro Presumido ou Lucro Real. "
        "Informe aliquota_icms_atual ou aliquota_iss_atual para maior precisao. "
        "Retorna projecao anual com premissas e disclaimers obrigatorios."
    ),
)
async def tool_simular_transicao_reforma_tributaria(
    faturamento_anual: float,
    setor: str,
    regime_atual: str,
    aliquota_icms_atual: float | None = None,
    aliquota_iss_atual: float | None = None,
    aliquota_pis_cofins: float | None = None,
) -> dict[str, Any]:
    """Simula o impacto financeiro da transicao para o novo sistema tributario (LC 214/2025).

    Projeta, ano a ano de 2026 a 2033, a carga tributaria estimada do regime antigo
    (PIS/COFINS + ICMS ou ISS) e do regime novo (CBS + IBS), conforme o cronograma de
    transicao da LC 214/2025: teste em 2026, CBS plena em 2027-2028, reducao gradual
    de ICMS/ISS de 2029 a 2032 e extincao total em 2033.

    Args:
        faturamento_anual: Receita bruta anual em reais. Deve ser positivo.
        setor: Setor da empresa. Aceita: "comércio", "serviços" ou "indústria".
        regime_atual: Regime tributario atual. Aceita: "Simples Nacional",
            "Lucro Presumido" ou "Lucro Real".
        aliquota_icms_atual: Aliquota do ICMS (%) vigente no estado da empresa.
            Obrigatoria para comercio/industria para maior precisao. Se None, assume 12%.
        aliquota_iss_atual: Aliquota do ISS (%) vigente no municipio da empresa.
            Obrigatoria para servicos para maior precisao. Se None, assume 5%.
        aliquota_pis_cofins: Aliquota efetiva de PIS/COFINS (%) sobre o faturamento.
            Se None, usa o padrao do regime informado (LP: 3,65%; LR: 9,25%; SN: 3,65%).

    Returns:
        dict com projecao anual 2026-2033, premissas utilizadas e avisos legais obrigatorios.
    """
    # Normaliza entradas aceitando variantes sem acento e em qualquer caixa
    # (ex.: "comercio", "COMERCIO", "Comércio" -> "comércio")
    setor_canonico = _normalizar_setor(setor)
    regime_canonico = _normalizar_regime(regime_atual)

    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_anual,
        setor=setor_canonico,
        regime_atual=regime_canonico,
        aliquota_icms_atual=aliquota_icms_atual,
        aliquota_iss_atual=aliquota_iss_atual,
        aliquota_pis_cofins=aliquota_pis_cofins,
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
    """Calcula score de risco para due diligence de fornecedor.

    Agrega o ComplianceReport do CNPJ com pesos conservadores de contratacao.
    Com criterios_estritos=True, aplica reducao adicional de 10 pontos para
    politicas anti-corrupcao (ex: Lei 12.846/2013).

    Args:
        cnpj: Numero do CNPJ com 14 digitos, com ou sem formatacao.
        criterios_estritos: Se True, aplica pesos mais rigorosos. Padrao: False.

    Returns:
        dict com score, recomendacao e justificativa da classificacao.
    """
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
    """Consulta em lote consolidada de compliance e risco para ate 50 CNPJs.

    Para cada CNPJ valido, executa analyze_cnpj_compliance + risk_score_supplier
    em paralelo. CNPJs com falha retornam erro individual sem abortar o lote.

    Args:
        cnpjs: Lista de CNPJs (max 50), com ou sem formatacao.
        criterios_estritos: Se True, usa pesos rigorosos no score de risco.

    Returns:
        dict com resultados por CNPJ e lista de erros individuais.
    """
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


# ---------------------------------------------------------------------------
# Modulos adicionais (Onda 1) - registrados via padrao register(app)
# ---------------------------------------------------------------------------

tabelas_tools.register(app)
bcb_tools.register(app)
cep_tools.register(app)
cnae_tools.register(app)
ibge_tools.register(app)
mei_tools.register(app)
empresa_tools.register(app)


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
