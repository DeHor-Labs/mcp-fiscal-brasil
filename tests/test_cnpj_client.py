"""Tests for CNPJ client response parsing edge cases."""

from mcp_fiscal_brasil.cnpj.client import CNPJClient


def test_parse_brasil_api_handles_null_collections_and_invalid_date() -> None:
    client = CNPJClient()

    response = client._parse_brasil_api(
        {
            "razao_social": "EMPRESA TESTE LTDA",
            "descricao_situacao_cadastral": "ATIVA",
            "natureza_juridica": "206-2 - Sociedade Empresaria Limitada",
            "cnaes_secundarios": None,
            "qsa": None,
            "data_inicio_atividade": "31/01/2024",
        },
        "12345678000195",
    )

    assert response.cnpj == "12345678000195"
    assert response.atividades_secundarias == []
    assert response.qsa == []
    assert response.data_abertura is None
    assert response.motivo_situacao_cadastral is None


def test_parse_brasil_api_mapeia_motivo_situacao() -> None:
    response = CNPJClient()._parse_brasil_api(
        {
            "razao_social": "EMPRESA TESTE LTDA",
            "descricao_situacao_cadastral": "INAPTA",
            "descricao_motivo_situacao_cadastral": "OMISSAO DE DECLARACOES",
        },
        "12345678000190",
    )
    assert response.motivo_situacao_cadastral == "OMISSAO DE DECLARACOES"


def test_parse_receita_ws_mapeia_motivo_situacao() -> None:
    response = CNPJClient()._parse_receita_ws(
        {"nome": "EMPRESA TESTE LTDA", "situacao": "INAPTA", "motivo_situacao": "OMISSAO"},
        "12345678000190",
    )
    assert response.motivo_situacao_cadastral == "OMISSAO"


def test_parse_cpfcnpj_mapeia_motivo_situacao() -> None:
    response = CNPJClient()._parse_cpfcnpj(
        {"razao": "EMPRESA TESTE LTDA", "situacao": {"nome": "Inapta", "motivo": "Omissão"}},
        "12345678000190",
    )
    assert response.motivo_situacao_cadastral == "Omissão"
