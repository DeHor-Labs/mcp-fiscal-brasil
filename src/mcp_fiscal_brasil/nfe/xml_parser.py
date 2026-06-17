"""Parser de XML de NFe (versão 4.00)."""

from datetime import datetime
from typing import cast

from lxml import etree

from ..shared.xml_utils import NS_NFE, parse_xml, xpath_text
from .schemas import EnderecoNFe, ItemNFe, NFeResponse, TotaisNFe, TotaisReformaNFe


def _find_any(
    element: etree._Element | None,
    namespaced_path: str,
    plain_path: str,
    ns: dict[str, str],
) -> etree._Element | None:
    if element is None:
        return None
    found = element.find(namespaced_path, ns)
    if found is not None:
        return found
    return element.find(plain_path)


def _findall_any(
    element: etree._Element | None,
    namespaced_path: str,
    plain_path: str,
    ns: dict[str, str],
) -> list[etree._Element]:
    if element is None:
        return []
    found = cast(list[etree._Element], element.findall(namespaced_path, ns))
    if found:
        return found
    return cast(list[etree._Element], element.findall(plain_path))


def _xpath_text_any(
    element: etree._Element | None,
    namespaced_xpath: str,
    plain_xpath: str,
    ns: dict[str, str],
) -> str | None:
    if element is None:
        return None
    return xpath_text(element, namespaced_xpath, ns) or xpath_text(element, plain_xpath, {})


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_endereco(element: etree._Element | None, ns: dict[str, str]) -> EnderecoNFe | None:
    if element is None:
        return None
    return EnderecoNFe(
        nome=_xpath_text_any(element, "nfe:xNome/text()", "xNome/text()", ns),
        cnpj=_xpath_text_any(element, "nfe:CNPJ/text()", "CNPJ/text()", ns),
        cpf=_xpath_text_any(element, "nfe:CPF/text()", "CPF/text()", ns),
        ie=_xpath_text_any(element, "nfe:IE/text()", "IE/text()", ns),
        logradouro=_xpath_text_any(
            element, "nfe:enderEmit/nfe:xLgr/text()", "enderEmit/xLgr/text()", ns
        )
        or _xpath_text_any(element, "nfe:enderDest/nfe:xLgr/text()", "enderDest/xLgr/text()", ns),
        número=_xpath_text_any(element, "nfe:enderEmit/nfe:nro/text()", "enderEmit/nro/text()", ns)
        or _xpath_text_any(element, "nfe:enderDest/nfe:nro/text()", "enderDest/nro/text()", ns),
        bairro=_xpath_text_any(
            element, "nfe:enderEmit/nfe:xBairro/text()", "enderEmit/xBairro/text()", ns
        )
        or _xpath_text_any(
            element, "nfe:enderDest/nfe:xBairro/text()", "enderDest/xBairro/text()", ns
        ),
        municipio=_xpath_text_any(
            element, "nfe:enderEmit/nfe:xMun/text()", "enderEmit/xMun/text()", ns
        )
        or _xpath_text_any(element, "nfe:enderDest/nfe:xMun/text()", "enderDest/xMun/text()", ns),
        uf=_xpath_text_any(element, "nfe:enderEmit/nfe:UF/text()", "enderEmit/UF/text()", ns)
        or _xpath_text_any(element, "nfe:enderDest/nfe:UF/text()", "enderDest/UF/text()", ns),
        cep=_xpath_text_any(element, "nfe:enderEmit/nfe:CEP/text()", "enderEmit/CEP/text()", ns)
        or _xpath_text_any(element, "nfe:enderDest/nfe:CEP/text()", "enderDest/CEP/text()", ns),
    )


def _parse_item(det: etree._Element, ns: dict[str, str]) -> ItemNFe:
    numero_str = det.get("nItem", "0")
    prod = _find_any(det, "nfe:prod", "prod", ns)
    imposto = _find_any(det, "nfe:imposto", "imposto", ns)

    icms_el = None
    ibscbs_el = None
    ibsuf_el = None
    ibsmun_el = None
    cbs_el = None
    is_el = None

    if imposto is not None:
        icms_group = _find_any(imposto, "nfe:ICMS", "ICMS", ns)
        if icms_group is not None and len(icms_group):
            icms_el = icms_group[0]  # ICMS00, ICMS10, etc.

        # Campos Reforma Tributária (NT 2025.002) - opcionais
        # Obrigatoriedade NF-e: produção CRT3 em 03/08/2026, homologação 01/07/2026,
        # Simples/MEI em 04/01/2027.
        ibscbs_el = _find_any(imposto, "nfe:IBSCBS", "IBSCBS", ns)
        if ibscbs_el is not None:
            # NT v1.40 usa tanto IBSUF quanto gIBSUF - aceita ambas as variantes.
            # Usa is not None explícito pra evitar FutureWarning do lxml (truth-testing).
            _ibsuf_g = _find_any(ibscbs_el, "nfe:gIBSUF", "gIBSUF", ns)
            ibsuf_el = (
                _ibsuf_g if _ibsuf_g is not None else _find_any(ibscbs_el, "nfe:IBSUF", "IBSUF", ns)
            )
            _ibsmun_g = _find_any(ibscbs_el, "nfe:gIBSMun", "gIBSMun", ns)
            ibsmun_el = (
                _ibsmun_g
                if _ibsmun_g is not None
                else _find_any(ibscbs_el, "nfe:IBSMun", "IBSMun", ns)
            )
            _cbs_g = _find_any(ibscbs_el, "nfe:gCBS", "gCBS", ns)
            cbs_el = _cbs_g if _cbs_g is not None else _find_any(ibscbs_el, "nfe:CBS", "CBS", ns)

        # IS (Imposto Seletivo) é IRMÃO de IBSCBS em det/imposto/IS per NT 2025.002.
        # Como fallback, busca também dentro de IBSCBS para compatibilidade
        # com implementações que posicionaram incorretamente.
        is_el = _find_any(imposto, "nfe:IS", "IS", ns)
        if is_el is None and ibscbs_el is not None:
            is_el = _find_any(ibscbs_el, "nfe:IS", "IS", ns)

    return ItemNFe(
        número=int(numero_str),
        codigo_produto=_xpath_text_any(prod, "nfe:cProd/text()", "cProd/text()", ns) or "",
        descrição=_xpath_text_any(prod, "nfe:xProd/text()", "xProd/text()", ns) or "",
        ncm=_xpath_text_any(prod, "nfe:NCM/text()", "NCM/text()", ns),
        cfop=_xpath_text_any(prod, "nfe:CFOP/text()", "CFOP/text()", ns) or "",
        unidade=_xpath_text_any(prod, "nfe:uCom/text()", "uCom/text()", ns) or "",
        quantidade=_safe_float(_xpath_text_any(prod, "nfe:qCom/text()", "qCom/text()", ns)) or 0.0,
        valor_unitario=_safe_float(_xpath_text_any(prod, "nfe:vUnCom/text()", "vUnCom/text()", ns))
        or 0.0,
        valor_total=_safe_float(_xpath_text_any(prod, "nfe:vProd/text()", "vProd/text()", ns))
        or 0.0,
        cst_icms=_xpath_text_any(icms_el, "nfe:CST/text()", "CST/text()", ns),
        aliquota_icms=_safe_float(_xpath_text_any(icms_el, "nfe:pICMS/text()", "pICMS/text()", ns)),
        valor_icms=_safe_float(_xpath_text_any(icms_el, "nfe:vICMS/text()", "vICMS/text()", ns)),
        # Reforma Tributária - IBS/CBS/IS (opcionais)
        aliquota_ibs_uf=_safe_float(
            _xpath_text_any(ibsuf_el, "nfe:pAliq/text()", "pAliq/text()", ns)
        ),
        valor_ibs_uf=_safe_float(
            _xpath_text_any(ibsuf_el, "nfe:vIBSUF/text()", "vIBSUF/text()", ns)
        ),
        aliquota_ibs_mun=_safe_float(
            _xpath_text_any(ibsmun_el, "nfe:pAliq/text()", "pAliq/text()", ns)
        ),
        valor_ibs_mun=_safe_float(
            _xpath_text_any(ibsmun_el, "nfe:vIBSMun/text()", "vIBSMun/text()", ns)
        ),
        aliquota_cbs=_safe_float(_xpath_text_any(cbs_el, "nfe:pAliq/text()", "pAliq/text()", ns)),
        valor_cbs=_safe_float(_xpath_text_any(cbs_el, "nfe:vCBS/text()", "vCBS/text()", ns)),
        # IS usa pIS/vIS (não pAliq como IBS/CBS) - NT 2025.002 seção UB04
        aliquota_is=_safe_float(_xpath_text_any(is_el, "nfe:pIS/text()", "pIS/text()", ns)),
        valor_is=_safe_float(_xpath_text_any(is_el, "nfe:vIS/text()", "vIS/text()", ns)),
    )


def parse_nfe_xml(xml_content: str | bytes, chave: str) -> NFeResponse:
    """
    Parseia o XML de uma NFe e retorna NFeResponse.

    Suporta NFe versão 4.00 com namespace do portal fiscal.
    """
    root = parse_xml(xml_content)
    ns = NS_NFE

    # A raiz pode ser <nfeProc> ou diretamente <NFe>
    nfe_el = root.find(".//nfe:NFe", ns)
    if nfe_el is None:
        nfe_el = root.find(".//NFe")
    if nfe_el is None:
        nfe_el = root

    inf_nfe = _find_any(nfe_el, ".//nfe:infNFe", ".//infNFe", ns)

    ide = _find_any(inf_nfe, "nfe:ide", "ide", ns)
    emit = _find_any(inf_nfe, "nfe:emit", "emit", ns)
    dest = _find_any(inf_nfe, "nfe:dest", "dest", ns)
    total = _find_any(inf_nfe, "nfe:total/nfe:ICMSTot", "total/ICMSTot", ns)
    total_reforma = _find_any(inf_nfe, "nfe:total/nfe:IBSCBSTot", "total/IBSCBSTot", ns)

    # Data de emissão
    data_emissao = None
    raw_dhemi = _xpath_text_any(ide, "nfe:dhEmi/text()", "dhEmi/text()", ns)
    if raw_dhemi:
        try:
            data_emissao = datetime.fromisoformat(raw_dhemi.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Protocolo de autorizacao
    prot_nfe = _find_any(root, ".//nfe:protNFe", ".//protNFe", ns)
    protocolo = _xpath_text_any(
        prot_nfe, "nfe:infProt/nfe:nProt/text()", "infProt/nProt/text()", ns
    )

    # Itens
    itens = []
    for det in _findall_any(inf_nfe, "nfe:det", "det", ns):
        itens.append(_parse_item(det, ns))

    # Totais
    totais = None
    if total is not None:
        totais = TotaisNFe(
            valor_produtos=_safe_float(
                _xpath_text_any(total, "nfe:vProd/text()", "vProd/text()", ns)
            ),
            valor_desconto=_safe_float(
                _xpath_text_any(total, "nfe:vDesc/text()", "vDesc/text()", ns)
            ),
            valor_frete=_safe_float(
                _xpath_text_any(total, "nfe:vFrete/text()", "vFrete/text()", ns)
            ),
            base_calculo_icms=_safe_float(
                _xpath_text_any(total, "nfe:vBC/text()", "vBC/text()", ns)
            ),
            valor_icms=_safe_float(_xpath_text_any(total, "nfe:vICMS/text()", "vICMS/text()", ns)),
            valor_icms_st=_safe_float(_xpath_text_any(total, "nfe:vST/text()", "vST/text()", ns)),
            valor_ipi=_safe_float(_xpath_text_any(total, "nfe:vIPI/text()", "vIPI/text()", ns)),
            valor_pis=_safe_float(_xpath_text_any(total, "nfe:vPIS/text()", "vPIS/text()", ns)),
            valor_cofins=_safe_float(
                _xpath_text_any(total, "nfe:vCOFINS/text()", "vCOFINS/text()", ns)
            ),
            valor_nota=_safe_float(_xpath_text_any(total, "nfe:vNF/text()", "vNF/text()", ns)),
        )

    # Totais Reforma Tributária (NT 2025.002 - Grupo W03/IBSCBSTot) - opcionais
    totais_reforma = None
    if total_reforma is not None:
        totais_reforma = TotaisReformaNFe(
            base_calculo_ibscbs=_safe_float(
                _xpath_text_any(total_reforma, "nfe:vBCIBSCBS/text()", "vBCIBSCBS/text()", ns)
            ),
            valor_ibs_uf=_safe_float(
                _xpath_text_any(total_reforma, "nfe:vIBSUF/text()", "vIBSUF/text()", ns)
            ),
            valor_ibs_mun=_safe_float(
                _xpath_text_any(total_reforma, "nfe:vIBSMun/text()", "vIBSMun/text()", ns)
            ),
            valor_ibs=_safe_float(
                _xpath_text_any(total_reforma, "nfe:vIBS/text()", "vIBS/text()", ns)
            ),
            valor_cbs=_safe_float(
                _xpath_text_any(total_reforma, "nfe:vCBS/text()", "vCBS/text()", ns)
            ),
            valor_is=_safe_float(
                _xpath_text_any(total_reforma, "nfe:vIS/text()", "vIS/text()", ns)
            ),
        )

    return NFeResponse(
        chave_acesso=chave,
        número=_xpath_text_any(ide, "nfe:nNF/text()", "nNF/text()", ns),
        serie=_xpath_text_any(ide, "nfe:serie/text()", "serie/text()", ns),
        modelo=_xpath_text_any(ide, "nfe:mod/text()", "mod/text()", ns) or "55",
        emitente=_parse_endereco(emit, ns),
        destinatario=_parse_endereco(dest, ns),
        data_emissao=data_emissao,
        natureza_operacao=_xpath_text_any(ide, "nfe:natOp/text()", "natOp/text()", ns),
        tipo_operacao=_xpath_text_any(ide, "nfe:tpNF/text()", "tpNF/text()", ns),
        itens=itens,
        totais=totais,
        totais_reforma=totais_reforma,
        protocolo_autorizacao=protocolo,
    )
