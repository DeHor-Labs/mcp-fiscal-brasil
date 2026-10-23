"""Testes do provedor premium opcional cpfcnpj.com.br.

Cobrem o transporte (status de sucesso/erro e ausencia de token), o mapeamento
das respostas de CNPJ (pacote 6) e de NF-e/NFC-e por chave (pacotes 100/102) e a
garantia de que, sem token configurado, o comportamento gratuito padrao nao muda.
"""

from typing import Any, ClassVar

import pytest

from mcp_fiscal_brasil._core import FiscalHTTPError, settings
from mcp_fiscal_brasil.cnpj.client import CNPJClient
from mcp_fiscal_brasil.nfe.client import NFEClient
from mcp_fiscal_brasil.shared import cpfcnpj as cpfcnpj_provider

# Amostras fieis ao contrato publicado em https://www.cpfcnpj.com.br/dev/openapi.json

CNPJ_6_SAMPLE: dict[str, Any] = {
    "status": 1,
    "cnpj": "00000000000191",
    "razao": "BANCO EXEMPLO SA",
    "fantasia": "BANCO EXEMPLO",
    "capitalSocial": 120000000000.0,
    "inicioAtividade": "1966-08-01",
    "email": "contato@exemplo.com.br",
    "naturezaJuridica": {"codigo": "2038", "descricao": "Sociedade de Economia Mista"},
    "simplesNacional": {"optante": "Não", "mei": "Não"},
    "matrizEndereco": {
        "cep": "70073901",
        "logradouro": "Setor Bancario Sul",
        "numero": "S/N",
        "complemento": "Edificio Sede",
        "bairro": "Asa Sul",
        "cidade": "Brasilia",
        "uf": "DF",
    },
    "telefones": [{"ddd": "61", "numero": "31070001"}],
    "situacao": {"id": 2, "nome": "Ativa", "data": "2005-11-03", "motivo": None},
    "cnae": {
        "fiscal": "6422100",
        "descricao": "Bancos multiplos com carteira comercial",
        "secundarias": [
            {"id": "6491300", "subclasse": "6491300", "descricao": "Sociedades de fomento"}
        ],
    },
    "porte": {"id": "05", "descricao": "Demais"},
    "socios": [
        {
            "cpf_cnpj_socio": "***000000**",
            "nome": "FULANO DE TAL",
            "qualificacao_socio": {"id": 10, "descricao": "Diretor"},
            "faixa_etaria": "51 a 60",
            "nome_representante": None,
            "qualificacao_representante": None,
        }
    ],
    "pacoteUsado": 6,
    "saldo": 999,
}

NFE_100_SAMPLE: dict[str, Any] = {
    "status": 1,
    "chave": "35170608530528000184550000000154301000771561",
    "dadosGerais": {"numero": "000.000.071", "versaoXml": "4.00"},
    "nfe": {
        "dadosDaNfe": {
            "modelo": "55",
            "serie": "1",
            "numero": "71",
            "dataDeEmissao": "01/01/2025 10:00:00",
            "dataHoraDeSaidaOuDaEntrada": "01/01/2025 12:00:00",
            "valorTotalDaNotaFiscal": "1.234,56",
        },
        "emissao": {
            "naturezaDaOperacao": "Venda de mercadoria",
            "finalidade": "NF-e normal",
            "tipoDaOperacao": "Saída",
        },
    },
    "situacaoAtual": {"situacao": "Autorizada", "ambienteAutorizacao": "Produção"},
    "eventosNfe": [
        {
            "evento": "Autorização de Uso",
            "protocolo": "135250000000071",
            "dataAutorizacao": "2025-01-01T10:00:05-03:00",
        }
    ],
    "emitente": {
        "nomeRazaoSocial": "Empresa Emitente Ltda",
        "cnpj": "00.000.000/0001-91",
        "endereco": "Rua A, 100",
        "bairroDistrito": "Centro",
        "cep": "00000-111",
        "municipio": "Sao Paulo",
        "uf": "SP",
        "inscricaoEstadual": "000000000000",
    },
    "destinatario": {
        "nomeRazaoSocial": "Cliente Final",
        "cpf": "000.000.000-00",
        "endereco": "Rua B, 200",
        "municipio": "Sao Paulo",
        "uf": "SP",
    },
    "pacoteUsado": 100,
    "saldo": 998,
}

NFCE_102_CHAVE = "35200114200166000187650010000000091000000097"


class _FakeHTTPClient:
    """HTTPClient falso para testes: devolve um corpo pre-definido, sem rede."""

    payload: ClassVar[dict[str, Any]] = {}
    ultimo_path: ClassVar[str | None] = None

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def __aenter__(self) -> "_FakeHTTPClient":
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        _FakeHTTPClient.ultimo_path = path
        return _FakeHTTPClient.payload


@pytest.fixture
def provedor_habilitado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Habilita o provedor premium com token de teste e HTTP mockado."""
    monkeypatch.setattr(settings, "cpfcnpj_token", "token_de_teste", raising=False)
    monkeypatch.setattr(cpfcnpj_provider, "HTTPClient", _FakeHTTPClient)


def test_provedor_desligado_por_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    # Isola o token do ambiente/.env: sem forcar o valor vazio, uma execucao com
    # CPFCNPJ_TOKEN definido faria provedor_configurado() retornar True.
    monkeypatch.setattr(settings, "cpfcnpj_token", "", raising=False)
    assert cpfcnpj_provider.provedor_configurado() is False


async def test_consultar_sem_token_levanta_erro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_token", "", raising=False)
    with pytest.raises(FiscalHTTPError):
        await cpfcnpj_provider.consultar(6, "00000000000191")


async def test_transporte_sucesso_status_1(provedor_habilitado: None) -> None:
    _FakeHTTPClient.payload = {"status": 1, "cnpj": "00000000000191"}
    data = await cpfcnpj_provider.consultar(6, "00000000000191")
    assert data["cnpj"] == "00000000000191"
    assert _FakeHTTPClient.ultimo_path == "/token_de_teste/6/00000000000191"


async def test_transporte_erro_status_0(provedor_habilitado: None) -> None:
    _FakeHTTPClient.payload = {"status": 0, "erro": "CNPJ inválido!", "erroCodigo": 200}
    with pytest.raises(FiscalHTTPError) as exc_info:
        await cpfcnpj_provider.consultar(6, "00000000000000")
    assert exc_info.value.status_code == 200
    assert "CNPJ inválido" in str(exc_info.value)


def test_parse_cnpj_pacote_6_mapeia_campos() -> None:
    resposta = CNPJClient()._parse_cpfcnpj(CNPJ_6_SAMPLE, "00000000000191")

    assert resposta.origem == "cpfcnpj.com.br"
    assert resposta.razao_social == "BANCO EXEMPLO SA"
    assert resposta.nome_fantasia == "BANCO EXEMPLO"
    assert resposta.situacao_cadastral == "Ativa"
    assert resposta.natureza_juridica == "2038 - Sociedade de Economia Mista"
    assert resposta.porte == "Demais"
    assert resposta.capital_social == 120000000000.0
    assert resposta.data_abertura is not None and resposta.data_abertura.year == 1966
    assert resposta.atividade_principal is not None
    assert resposta.atividade_principal.código == "6422100"
    assert len(resposta.atividades_secundarias) == 1
    assert resposta.endereco is not None and resposta.endereco.municipio == "Brasilia"
    assert resposta.telefone == "(61) 31070001"
    assert resposta.simples_nacional is False
    assert resposta.mei is False
    assert len(resposta.qsa) == 1
    assert resposta.qsa[0].qualificacao == "Diretor"
    assert resposta.qsa[0].faixa_etaria == "51 a 60"


async def test_cnpj_usa_provedor_quando_configurado(provedor_habilitado: None) -> None:
    _FakeHTTPClient.payload = CNPJ_6_SAMPLE
    resposta = await CNPJClient().consultar("00.000.000/0001-91")
    assert resposta.origem == "cpfcnpj.com.br"
    assert _FakeHTTPClient.ultimo_path == "/token_de_teste/6/00000000000191"


async def test_cnpj_faz_fallback_quando_provedor_falha(
    provedor_habilitado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeHTTPClient.payload = {"status": 0, "erro": "Créditos insuficientes!", "erroCodigo": 1001}

    async def _fake_brasil_api(self: CNPJClient, cnpj: str) -> Any:
        from mcp_fiscal_brasil.cnpj.schemas import CNPJResponse

        return CNPJResponse(
            cnpj=cnpj,
            razao_social="EMPRESA FALLBACK",
            situacao_cadastral="ATIVA",
            natureza_juridica="LTDA",
            origem="BrasilAPI",
        )

    monkeypatch.setattr(CNPJClient, "_consultar_brasil_api", _fake_brasil_api)
    resposta = await CNPJClient().consultar("00000000000191")
    assert resposta.origem == "BrasilAPI"


def test_parse_nfe_pacote_100_mapeia_campos() -> None:
    chave = "35170608530528000184550000000154301000771561"
    resposta = NFEClient()._parse_cpfcnpj(NFE_100_SAMPLE, chave)

    assert resposta.chave_acesso == chave
    assert resposta.modelo == "55"
    assert resposta.serie == "1"
    assert resposta.número == "71"
    assert resposta.situacao == "Autorizada"
    assert resposta.natureza_operacao == "Venda de mercadoria"
    assert resposta.protocolo_autorizacao == "135250000000071"
    assert resposta.data_emissao is not None and resposta.data_emissao.year == 2025
    assert resposta.totais is not None and resposta.totais.valor_nota == 1234.56
    assert resposta.emitente is not None
    assert resposta.emitente.cnpj == "00000000000191"
    assert resposta.emitente.nome == "Empresa Emitente Ltda"
    assert resposta.destinatario is not None and resposta.destinatario.cpf == "00000000000"


def test_pacote_cpfcnpj_roteia_por_modelo() -> None:
    client = NFEClient()
    assert client._pacote_cpfcnpj("35170608530528000184550000000154301000771561") == 100
    assert client._pacote_cpfcnpj(NFCE_102_CHAVE) == 102
    assert client._pacote_cpfcnpj("3517060853052800018499") is None


async def test_nfce_modelo_65_usa_pacote_102(provedor_habilitado: None) -> None:
    _FakeHTTPClient.payload = {
        "status": 1,
        "chave": NFCE_102_CHAVE,
        "nfe": {"dadosDaNfe": {"modelo": "65", "serie": "1", "numero": "9"}},
        "situacaoAtual": {"situacao": "Autorizada"},
    }
    resposta = await NFEClient().consultar_por_chave(NFCE_102_CHAVE)
    assert resposta.modelo == "65"
    assert _FakeHTTPClient.ultimo_path == f"/token_de_teste/102/{NFCE_102_CHAVE}"


def _gerar_cnpj_alfanumerico(base12: str) -> str:
    """Gera um CNPJ alfanumerico com os 2 DVs corretos (IN RFB 2.229/2024)."""
    valores = [ord(c) - 48 for c in base12]
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(valores[i] * pesos1[i] for i in range(12))
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto
    valores2 = [*valores, dv1]
    soma = sum(valores2[i] * pesos2[i] for i in range(13))
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto
    return f"{base12}{dv1}{dv2}"


def test_cnpj_alfanumerico_gerado_tem_dv_valido() -> None:
    from mcp_fiscal_brasil.shared.validators import (
        validate_cnpj_alfanumerico,
        validate_cnpj_qualquer,
    )

    cnpj = _gerar_cnpj_alfanumerico("12ABC34501DE")
    assert validate_cnpj_alfanumerico(cnpj) is True
    # DV alterado deve invalidar
    dv_errado = cnpj[:13] + str((int(cnpj[13]) + 1) % 10)
    assert validate_cnpj_alfanumerico(dv_errado) is False
    # CNPJ numerico valido continua aceito
    assert validate_cnpj_qualquer("33.000.167/0001-01") is True


async def test_cnpj_alfanumerico_usa_provedor(provedor_habilitado: None) -> None:
    # CNPJ alfanumerico com mascara deve ser normalizado (letras preservadas em
    # maiusculas) e enviado inteiro no caminho da consulta.
    _FakeHTTPClient.payload = {"status": 1, "cnpj": "12ABC34501DE35"}
    await CNPJClient().consultar("12.ABC.345/01DE-35")
    assert _FakeHTTPClient.ultimo_path == "/token_de_teste/6/12ABC34501DE35"


def test_limitador_cpfcnpj_compartilhado() -> None:
    # Duas instancias/chamadas devem compartilhar o mesmo AsyncLimiter (singleton).
    limitador = cpfcnpj_provider._get_limiter()
    assert limitador is cpfcnpj_provider._get_limiter()
    cliente_a = cpfcnpj_provider._http_client()
    cliente_b = cpfcnpj_provider._http_client()
    assert cliente_a._limiter is cliente_b._limiter
    assert cliente_a._limiter is limitador


def test_parse_nfe_preserva_cnpj_alfanumerico_de_emitente_e_destinatario() -> None:
    """CNPJ alfanumerico (IN RFB 2.229/2024) nao pode perder as letras no parse da NF-e."""
    chave = "35170608530528000184550000000154301000771561"
    cnpj_alfa = _gerar_cnpj_alfanumerico("12ABC34501DE")
    amostra = {
        **NFE_100_SAMPLE,
        "emitente": {**NFE_100_SAMPLE["emitente"], "cnpj": _mascara_cnpj(cnpj_alfa)},
        "destinatario": {
            "nomeRazaoSocial": "Cliente PJ",
            "cnpj": cnpj_alfa.lower(),
            "endereco": "Rua C, 300",
            "municipio": "Sao Paulo",
            "uf": "SP",
        },
    }

    resposta = NFEClient()._parse_cpfcnpj(amostra, chave)

    assert resposta.emitente is not None
    assert resposta.emitente.cnpj == cnpj_alfa
    assert resposta.destinatario is not None
    assert resposta.destinatario.cnpj == cnpj_alfa
    assert resposta.destinatario.cpf is None


def _mascara_cnpj(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
