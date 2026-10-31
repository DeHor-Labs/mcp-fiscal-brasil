from __future__ import annotations

from datetime import date

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
_URL_REMISSAO = (
    "https://www.gov.br/pgfn/pt-br/servicos/perguntas-frequentes/"
    "perguntas-frequentes-perdao-do-mei"
)

_LINKS = {
    "e_cac": _URL_ECAC,
    "pgmei": _URL_PGMEI,
    "dasn_simei": _URL_DASN,
    "comprovante_cnpj": _URL_COMPROVANTE,
    "remissao_mei": _URL_REMISSAO,
}

_ANO_MIN_DASN = 2007


def _anos_texto(anos: list[int]) -> str:
    if not anos:
        return "cada ano-calendário omitido"
    return ", ".join(str(ano) for ano in anos)


def _validar_anos_omitidos(anos: list[int] | None) -> list[int]:
    if not anos:
        return []
    ano_max = date.today().year - 1
    normalizados = sorted({int(a) for a in anos})
    invalidos = [a for a in normalizados if a < _ANO_MIN_DASN or a > ano_max]
    if invalidos:
        raise ValueError(
            f"anos_omitidos fora do intervalo declarável "
            f"({_ANO_MIN_DASN}–{ano_max}): {invalidos}"
        )
    return normalizados


def _normalizar_cnpj_opcional(cnpj: str | None) -> str | None:
    if cnpj is None:
        return None
    if not cnpj.strip():
        raise ValueError("CNPJ inválido: string vazia")
    if not validate_cnpj_qualquer(cnpj):
        raise ValueError(f"CNPJ inválido: '{cnpj}'")
    return normalizar_cnpj(cnpj)


def orientar_regularizacao_mei(
    request: RegularizacaoMeiRequest,
) -> RegularizacaoMeiResponse:
    cnpj_norm = _normalizar_cnpj_opcional(request.cnpj)
    anos = _validar_anos_omitidos(request.anos_omitidos)
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
            titulo="Regularizar ano a ano (antigo → recente)",
            detalhe=(
                f"Para cada ano omitido ({anos_txt}), do mais antigo ao mais recente: "
                "(a) apure no PGMEI os períodos mensais daquele ano e pague o DAS "
                "somente se exigido para aquele ano; "
                "(b) transmita a DASN-SIMEI daquele ano; "
                "(c) só então avance ao próximo ano. "
                f"{receita_txt} Prazo normal da DASN: até o último dia de maio "
                "do ano seguinte ao ano-calendário. Guarde o recibo de cada ano."
            ),
            url=_URL_DASN,
        ),
        RegularizacaoMeiPasso(
            ordem=3,
            titulo="Conferir remissão antes de pagar DAS antigos",
            detalhe=(
                "Antes de quitar integralmente DAS antigos, verifique elegibilidade "
                "à remissão da parcela previdenciária (LC 238/2026; efeitos a partir "
                "de 01/01/2027). Até lá os débitos seguem exigíveis; valores já pagos "
                "não são restituídos; ICMS/ISS não entram na remissão."
            ),
            url=_URL_REMISSAO,
        ),
        RegularizacaoMeiPasso(
            ordem=4,
            titulo="Pagar DAS devidos no PGMEI",
            detalhe=(
                "No PGMEI, emita e pague os DAS mensais devidos dos anos listados. "
                "INSS do MEI é devido mesmo sem receita. Só gerar o DAS não quita "
                "o débito. O pagamento do DAS não é condição para transmitir a DASN."
            ),
            url=_URL_PGMEI,
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
            "(mínimo R$ 50,00 — LC 123/2006 art. 38). Após a transmissão, "
            "verifique e pague o DARF da multa no prazo; o pagamento no prazo "
            "pode reduzir a multa mínima de R$ 50,00 para R$ 25,00."
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
