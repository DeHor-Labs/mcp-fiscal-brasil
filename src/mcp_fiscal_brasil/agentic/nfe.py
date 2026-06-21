"""Validacao consolidada de NFe (XML + chave + emissor)."""

from __future__ import annotations

from pathlib import Path

from mcp_fiscal_brasil._core import get_logger

from ..cnpj.client import CNPJClient
from ..nfe.tools import validar_chave_nfe
from ..nfe.xml_parser import parse_nfe_xml
from ..shared.validators import validar_caminho_arquivo
from .schemas import NFeValidationIssue, NFeValidationReport

logger = get_logger(__name__)


async def validate_nfe_full(xml_path: str | Path) -> NFeValidationReport:
    """
    Validacao consolidada de uma NFe (XML).

    Executa em sequencia:
    1. Parse estrutural do XML (lxml)
    2. Validacao do digito verificador da chave de acesso
    3. Verificacao do CNPJ emissor (situacao ativa via Receita)

    Args:
        xml_path: Caminho para arquivo XML da NFe.

    Returns:
        NFeValidationReport com chave, validade, issues e resumo.

    Exemplo:
        report = await validate_nfe_full("/tmp/nota.xml")
        if not report.valida_estruturalmente or report.issues:
            # rejeitar nota
            ...
    """
    path = validar_caminho_arquivo(xml_path, label="Arquivo XML")
    issues: list[NFeValidationIssue] = []
    xml_content = path.read_bytes()

    valida_estrut = False
    chave_acesso = ""
    cnpj_emissor: str | None = None
    cnpj_destinatario: str | None = None
    valor_total: float | None = None
    data_emissao = None
    nfe_data = None

    try:
        # Chave temporaria, parser preenche corretamente
        nfe_data = parse_nfe_xml(xml_content, chave="")
        chave_acesso = nfe_data.chave_acesso or ""
        cnpj_emissor = getattr(nfe_data.emitente, "cnpj", None) if nfe_data.emitente else None
        cnpj_destinatario = (
            getattr(nfe_data.destinatario, "cnpj", None) if nfe_data.destinatario else None
        )
        valor_total = nfe_data.totais.valor_nota if nfe_data.totais else None
        data_emissao = nfe_data.data_emissao.date() if nfe_data.data_emissao else None
        valida_estrut = True
    except Exception as exc:
        issues.append(
            NFeValidationIssue(
                severidade="critico",
                código="XML_PARSE_ERROR",
                descrição=f"Falha ao parsear XML: {exc}",
            )
        )

    # Validacao da chave
    chave_consistente = False
    if chave_acesso:
        try:
            chave_result = await validar_chave_nfe(chave_acesso)
            chave_consistente = bool(chave_result.get("válida", False))
            if not chave_consistente:
                issues.append(
                    NFeValidationIssue(
                        severidade="alto",
                        código="CHAVE_INVALIDA",
                        descrição="Digito verificador da chave de acesso não confere.",
                        campo="chave_acesso",
                    )
                )
        except Exception as exc:
            issues.append(
                NFeValidationIssue(
                    severidade="medio",
                    código="CHAVE_VALIDACAO_FALHOU",
                    descrição=f"Não foi possivel validar chave: {exc}",
                )
            )

    # Verificacao do emissor
    emissor_ativo: bool | None = None
    if cnpj_emissor:
        try:
            cnpj_client = CNPJClient()
            emissor_data = await cnpj_client.consultar(cnpj_emissor)
            situacao = (emissor_data.situacao_cadastral or "").lower()
            emissor_ativo = "ativ" in situacao
            if not emissor_ativo:
                issues.append(
                    NFeValidationIssue(
                        severidade="alto",
                        código="EMISSOR_INATIVO",
                        descrição=f"CNPJ emissor com situacao '{emissor_data.situacao_cadastral}'.",
                        campo="emit/CNPJ",
                    )
                )
        except Exception as exc:
            logger.warning("nfe_emissor_lookup_failed", error=str(exc))
            emissor_ativo = None

    if valida_estrut and not issues:
        resumo = f"NFe válida estruturalmente, chave {chave_acesso} consistente, emissor ativo."
    elif valida_estrut:
        resumo = f"NFe parseou ok mas tem {len(issues)} issue(s) ({issues[0].código})."
    else:
        resumo = "NFe falhou no parse XML. Verifique arquivo e schema."

    return NFeValidationReport(
        chave_acesso=chave_acesso,
        valida_estruturalmente=valida_estrut,
        chave_consistente=chave_consistente,
        emissor_ativo=emissor_ativo,
        issues=issues,
        cnpj_emissor=cnpj_emissor,
        cnpj_destinatario=cnpj_destinatario,
        valor_total=valor_total,
        data_emissao=data_emissao,
        resumo=resumo,
    )
