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
    urls = " ".join(filter(None, [p.url for p in response.passos]))
    assert "receita.fazenda.gov.br" in urls
    assert "pgmei" in response.links_oficiais["pgmei"].lower()
    assert "dasnsimei" in response.links_oficiais["dasn_simei"].lower()
    assert any("DASN" in a or "Gov.br" in a for a in response.avisos)
    assert any("multa" in a.lower() and "50" in a for a in response.avisos)
    assert "0,00" in response.passos[2].detalhe
    assert "maio" in response.passos[2].detalhe.casefold()
    assert "pague" in response.passos[1].detalhe.casefold() or "pagar" in response.passos[1].titulo.casefold()
    assert "baixa de ofício" in response.passos[4].detalhe.casefold()


def test_orientar_regularizacao_mei_cnpj_invalido() -> None:
    with pytest.raises(ValueError, match="CNPJ inválido"):
        orientar_regularizacao_mei(RegularizacaoMeiRequest(cnpj="123"))


@pytest.mark.asyncio
async def test_tool_orientar_regularizacao_mei() -> None:
    result = await tool_orientar(anos_omitidos=[2024], receita_zero=False)
    assert result.status == "consulta_manual_necessaria"
    assert result.anos_omitidos == [2024]
    assert "0,00" not in result.passos[2].detalhe
