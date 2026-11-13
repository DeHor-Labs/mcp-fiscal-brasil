from datetime import date

import pytest

from mcp_fiscal_brasil.mei.regularizacao import orientar_regularizacao_mei
from mcp_fiscal_brasil.mei.schemas import RegularizacaoMeiRequest
from mcp_fiscal_brasil.mei.tools import orientar_regularizacao_mei as tool_orientar


def test_orientar_regularizacao_mei_passos_e_links() -> None:
    response = orientar_regularizacao_mei(
        RegularizacaoMeiRequest(
            cnpj="27.496.821/0001-17",
            anos_omitidos=[2021, 2025, 2023],
            receita_zero=True,
        )
    )
    assert response.status == "consulta_manual_necessaria"
    assert response.cnpj == "27496821000117"
    assert response.anos_omitidos == [2021, 2023, 2025]
    assert len(response.passos) == 5
    assert response.passos[0].ordem == 1
    assert "e-CAC" in response.passos[0].titulo or "e-CAC" in response.passos[0].detalhe
    assert (
        "ano a ano" in response.passos[1].titulo.casefold()
        or "antigo" in response.passos[1].titulo.casefold()
    )
    assert "0,00" in response.passos[1].detalhe
    assert "maio" in response.passos[1].detalhe.casefold()
    assert (
        "remiss" in response.passos[2].titulo.casefold()
        or "remiss" in response.passos[2].detalhe.casefold()
    )
    assert "não é condição" in response.passos[3].detalhe.casefold()
    assert "baixa de ofício" in response.passos[4].detalhe.casefold()
    urls = " ".join(filter(None, [p.url for p in response.passos]))
    assert "receita.fazenda.gov.br" in urls
    assert response.links_oficiais["e_cac"] == (
        "https://cav.receita.fazenda.gov.br/autenticacao/login"
    )
    assert response.links_oficiais["pgmei"] == (
        "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/"
        "pgmei.app/Identificacao"
    )
    assert response.links_oficiais["dasn_simei"] == (
        "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/"
        "dasnsimei.app/Identificacao"
    )
    assert response.links_oficiais["comprovante_cnpj"] == (
        "https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp"
    )
    assert response.links_oficiais["remissao_mei"] == (
        "https://www.gov.br/pgfn/pt-br/servicos/perguntas-frequentes/"
        "perguntas-frequentes-perdao-do-mei"
    )
    assert any("DARF" in a and "25,00" in a for a in response.avisos)
    assert any("multa" in a.lower() and "50" in a for a in response.avisos)


def test_orientar_regularizacao_mei_cnpj_invalido() -> None:
    with pytest.raises(ValueError, match="CNPJ inválido"):
        orientar_regularizacao_mei(RegularizacaoMeiRequest(cnpj="123"))


def test_orientar_regularizacao_mei_cnpj_vazio() -> None:
    with pytest.raises(ValueError, match="vazia"):
        orientar_regularizacao_mei(RegularizacaoMeiRequest(cnpj=""))


@pytest.mark.parametrize("ano", [1999, 2007, 2008, date.today().year])
def test_orientar_regularizacao_mei_ano_invalido(ano: int) -> None:
    with pytest.raises(ValueError, match="anos_omitidos"):
        orientar_regularizacao_mei(RegularizacaoMeiRequest(anos_omitidos=[ano]))


def test_orientar_regularizacao_mei_aceita_2009() -> None:
    response = orientar_regularizacao_mei(RegularizacaoMeiRequest(anos_omitidos=[2009]))
    assert response.anos_omitidos == [2009]


def test_orientar_regularizacao_mei_informa_condicao_da_remissao() -> None:
    response = orientar_regularizacao_mei(RegularizacaoMeiRequest())
    detalhe = response.passos[2].detalhe.casefold()
    assert "seis meses" in detalhe
    assert "cancela a remissão" in detalhe


@pytest.mark.asyncio
async def test_tool_orientar_regularizacao_mei() -> None:
    result = await tool_orientar(anos_omitidos=[2024], receita_zero=False)
    assert result.status == "consulta_manual_necessaria"
    assert result.anos_omitidos == [2024]
    assert "0,00" not in result.passos[1].detalhe
