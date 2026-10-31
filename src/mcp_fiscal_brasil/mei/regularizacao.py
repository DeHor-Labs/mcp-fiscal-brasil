from __future__ import annotations

from mcp_fiscal_brasil.shared.validators import normalizar_cnpj, validate_cnpj_qualquer

from .schemas import (
    RegularizacaoMeiPasso,
    RegularizacaoMeiRequest,
    RegularizacaoMeiResponse,
)

_URL_ECAC = "https://cav.receita.fazenda.gov.br/autenticacao/login"
_URL_PGMEI = (
    "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/"
    "pgmei.app/Identificacao"
)
_URL_DASN = (
    "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/"
    "dasnsimei.app/Identificacao"
)
_URL_COMPROVANTE = (
    "https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp"
)

_LINKS = {
    "e_cac": _URL_ECAC,
    "pgmei": _URL_PGMEI,
    "dasn_simei": _URL_DASN,
    "comprovante_cnpj": _URL_COMPROVANTE,
}


def _anos_texto(anos: list[int]) -> str:
    if not anos:
        return "cada ano-calendário omitido"
    return ", ".join(str(ano) for ano in anos)


def orientar_regularizacao_mei(
    request: RegularizacaoMeiRequest,
) -> RegularizacaoMeiResponse:
    cnpj_norm: str | None = None
    if request.cnpj:
        if not validate_cnpj_qualquer(request.cnpj):
            raise ValueError(f"CNPJ inválido: '{request.cnpj}'")
        cnpj_norm = normalizar_cnpj(request.cnpj)

    anos = sorted({int(a) for a in (request.anos_omitidos or []) if int(a) > 2000})
    receita_txt = (
        "Informe receita bruta anual 0,00 se não houve movimento."
        if request.receita_zero
        else "Informe a receita bruta anual real do ano-calendário."
    )
    anos_txt = _anos_texto(anos)

    passos = [
        RegularizacaoMeiPasso(
            ordem=1,
            titulo="Abrir o e-CAC",
            detalhe=(
                "Acesse o e-CAC com conta Gov.br e confira pendências / "
                "declarações não entregues (DASN-SIMEI). Use só se o CNPJ "
                "for/foi optante pelo Simei (MEI)."
            ),
            url=_URL_ECAC,
        ),
        RegularizacaoMeiPasso(
            ordem=2,
            titulo="Gerar e pagar DAS no PGMEI se a DASN bloquear",
            detalhe=(
                "Se aparecer aviso pedindo DAS do período, abra o PGMEI, "
                f"emita e pague o DAS de {anos_txt} (INSS mensal do MEI "
                "é devido mesmo sem receita). Só gerar o DAS não quita o débito."
            ),
            url=_URL_PGMEI,
        ),
        RegularizacaoMeiPasso(
            ordem=3,
            titulo="Entregar DASN-SIMEI",
            detalhe=(
                f"Transmita a DASN-SIMEI de {anos_txt}. {receita_txt} "
                "Prazo normal: até o último dia de maio do ano seguinte ao "
                "ano-calendário. Guarde o recibo de cada ano."
            ),
            url=_URL_DASN,
        ),
        RegularizacaoMeiPasso(
            ordem=4,
            titulo="Repetir por ano omitido",
            detalhe=(
                "Conclua PGMEI (gerar+pagar, se necessário) + DASN para todos "
                "os anos listados no e-CAC, do mais antigo ao mais recente. "
                "Inatividade não dispensa a DASN-SIMEI."
            ),
            url=None,
        ),
        RegularizacaoMeiPasso(
            ordem=5,
            titulo="Reemitir comprovante CNPJ",
            detalhe=(
                "Após sanar todas as omissões, emita o comprovante de inscrição "
                "e situação cadastral. A RFB processa a reversão de INAPTA "
                "diariamente; APIs públicas podem atrasar vs e-CAC. INAPTA "
                "prolongada pode levar a baixa de ofício."
            ),
            url=_URL_COMPROVANTE,
        ),
    ]

    avisos = [
        "Não há API pública para login Gov.br; esta tool só orienta com URLs oficiais.",
        (
            "Atraso ou omissão da DASN-SIMEI sujeita a multa "
            "(mínimo R$ 50,00 — LC 123/2006 art. 38)."
        ),
        "Remissão/parcelamento de INSS não dispensa a entrega da DASN-SIMEI.",
        (
            "Use receita_zero=false se houve faturamento; o default true serve "
            "apenas a CNPJ abandonado sem movimento."
        ),
        "Consultas públicas (BrasilAPI etc.) podem atrasar em relação ao e-CAC.",
    ]

    return RegularizacaoMeiResponse(
        status="consulta_manual_necessaria",
        cnpj=cnpj_norm,
        anos_omitidos=anos,
        receita_zero=request.receita_zero,
        passos=passos,
        avisos=avisos,
        links_oficiais=_LINKS,
    )
