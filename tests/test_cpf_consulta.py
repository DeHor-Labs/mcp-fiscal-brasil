"""Testes da consulta de situacao cadastral de CPF (consultar_cpf, premium opt-in).

Cobrem a tool, o client, a API REST e o SDK: sucesso por pacote (26/8/3/1), ausencia
de token, digito verificador invalido sem chamada ao provedor, erro 102 (CPF valido mas
inexistente), o mapeamento das situacoes cadastrais + o derivado apto_emissao e a politica
de privacidade (CPF mascarado em log, PDF fora de log, resposta sem campos operacionais).

Amostras fieis ao contrato publicado em https://www.cpfcnpj.com.br/dev/ (openapi.json).
"""

from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from mcp_fiscal_brasil._core import FiscalError, settings
from mcp_fiscal_brasil._core.config import Settings
from mcp_fiscal_brasil.api import app
from mcp_fiscal_brasil.cpf import client as cpf_client
from mcp_fiscal_brasil.cpf.client import CPFClient, mascarar_cpf
from mcp_fiscal_brasil.cpf.tools import consultar_cpf_tool
from mcp_fiscal_brasil.sdk import FiscalBrasil
from mcp_fiscal_brasil.shared import cpfcnpj as cpfcnpj_provider

# CPF de teste com digito verificador valido (dados ficticios no token de testes).
CPF_TESTE = "11144477735"

CPF_26_SAMPLE: dict[str, Any] = {
    "status": 1,
    "cpf": "111.444.777-35",
    "nome": "FULANO DE TAL",
    "nascimento": "01/01/1990",
    "situacao": "Regular",
    "situacaoDigito": "00",
    "pacoteUsado": 26,
    "saldo": 900,
    "consultaID": "1234567890123456",
}

CPF_8_SAMPLE: dict[str, Any] = {
    "status": 1,
    "cpf": "111.444.777-35",
    "nome": "FULANO DE TAL",
    "nomeSocial": "",
    "nascimento": "01/01/1990",
    "situacao": "Cancelada",
    "situacaoDigito": "03",
    "situacaoMotivo": "TITULAR FALECIDO",
    "situacaoAnoObito": 2015,
    "situacaoInscricao": "anterior a 10/11/1990",
    "situacaoComprovante": "1A1A.2B2B.3C3C.4D4D",
    "situacaoComprovanteEmissao": "01/01/2025 10:00:00",
    "situacaoComprovantePdf": "JVBERi0xLjQKJVBERg==",
    "pacoteUsado": 8,
    "saldo": 899,
    "consultaID": "1234567890123457",
    "delay": 2.1,
}

CPF_3_SAMPLE: dict[str, Any] = {
    "status": 1,
    "cpf": "111.444.777-35",
    "nome": "FULANO DE TAL",
    "nascimento": "01/01/1990",
    "genero": "M",
    "endereco": "RUA DAS FLORES",
    "numero": "100",
    "complemento": "APTO 1",
    "bairro": "CENTRO",
    "cep": "01001000",
    "cidade": "SAO PAULO",
    "uf": "SP",
    "ibge": "3550308",
    "pacoteUsado": 3,
    "saldo": 898,
}

CPF_1_SAMPLE: dict[str, Any] = {
    "status": 1,
    "cpf": "111.444.777-35",
    "nome": "FULANO DE TAL",
    "pacoteUsado": 1,
    "saldo": 897,
}


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


class _RecordingLogger:
    """Logger falso que registra os eventos e kwargs, para inspecionar PII."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def info(self, event: str, **kwargs: Any) -> None:
        self.eventos.append((event, kwargs))

    def warning(self, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, *args: Any, **kwargs: Any) -> None:
        pass


@pytest.fixture
def provedor_habilitado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Habilita o provedor premium com token de teste, pacote 26 e HTTP mockado."""
    monkeypatch.setattr(settings, "cpfcnpj_token", "token_de_teste", raising=False)
    monkeypatch.setattr(settings, "cpfcnpj_cpf_packet", 26, raising=False)
    monkeypatch.setattr(cpfcnpj_provider, "HTTPClient", _FakeHTTPClient)
    _FakeHTTPClient.ultimo_path = None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_pacote_cpf_padrao_26() -> None:
    assert Settings().cpfcnpj_cpf_packet == 26


@pytest.mark.parametrize("pacote", [1, 3, 8, 26])
def test_config_pacote_cpf_aceita_validos(pacote: int) -> None:
    assert Settings(cpfcnpj_cpf_packet=pacote).cpfcnpj_cpf_packet == pacote


def test_config_pacote_cpf_rejeita_invalido() -> None:
    with pytest.raises(ValueError):
        Settings(cpfcnpj_cpf_packet=9)


# ---------------------------------------------------------------------------
# Mascaramento
# ---------------------------------------------------------------------------


def test_mascarar_cpf_preserva_apenas_dv() -> None:
    assert mascarar_cpf("11144477735") == "***.***.***-35"
    assert mascarar_cpf("111.444.777-35") == "***.***.***-35"
    assert mascarar_cpf("123") == "***.***.***-**"


# ---------------------------------------------------------------------------
# Tool: sucesso por pacote
# ---------------------------------------------------------------------------


async def test_tool_pacote_26_situacao_regular(provedor_habilitado: None) -> None:
    _FakeHTTPClient.payload = CPF_26_SAMPLE
    cadastro = await consultar_cpf_tool(CPF_TESTE)
    assert cadastro.origem == "cpfcnpj.com.br"
    assert cadastro.cpf == "***.***.***-35"
    assert cadastro.nome == "FULANO DE TAL"
    assert cadastro.nascimento == "01/01/1990"
    assert cadastro.situacao is not None
    assert cadastro.situacao.codigo == "00"
    assert cadastro.situacao.descricao == "Regular"
    assert cadastro.apto_emissao is True
    assert _FakeHTTPClient.ultimo_path == f"/token_de_teste/26/{CPF_TESTE}"


async def test_tool_pacote_8_comprovante_e_obito(
    provedor_habilitado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_cpf_packet", 8, raising=False)
    _FakeHTTPClient.payload = CPF_8_SAMPLE
    cadastro = await consultar_cpf_tool(CPF_TESTE)
    assert cadastro.situacao is not None
    assert cadastro.situacao.codigo == "03"
    assert cadastro.situacao.descricao == "Titular Falecido"
    assert cadastro.situacao.motivo == "TITULAR FALECIDO"
    assert cadastro.situacao.ano_obito == 2015
    assert cadastro.apto_emissao is False
    assert cadastro.comprovante is not None
    assert cadastro.comprovante.numero == "1A1A.2B2B.3C3C.4D4D"
    assert cadastro.comprovante.pdf_base64 == "JVBERi0xLjQKJVBERg=="
    assert _FakeHTTPClient.ultimo_path == f"/token_de_teste/8/{CPF_TESTE}"


async def test_tool_pacote_3_endereco(
    provedor_habilitado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_cpf_packet", 3, raising=False)
    _FakeHTTPClient.payload = CPF_3_SAMPLE
    cadastro = await consultar_cpf_tool(CPF_TESTE)
    assert cadastro.genero == "M"
    assert cadastro.endereco is not None
    assert cadastro.endereco.logradouro == "RUA DAS FLORES"
    assert cadastro.endereco.cidade == "SAO PAULO"
    assert cadastro.endereco.uf == "SP"
    assert cadastro.endereco.ibge == "3550308"
    # Pacote 3 nao traz situacao: apto_emissao fica indeterminado.
    assert cadastro.situacao is None
    assert cadastro.apto_emissao is None


async def test_tool_pacote_1_so_nome(
    provedor_habilitado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_cpf_packet", 1, raising=False)
    _FakeHTTPClient.payload = CPF_1_SAMPLE
    cadastro = await consultar_cpf_tool(CPF_TESTE)
    assert cadastro.nome == "FULANO DE TAL"
    assert cadastro.situacao is None
    assert cadastro.endereco is None
    assert cadastro.comprovante is None


# ---------------------------------------------------------------------------
# Tool: erros
# ---------------------------------------------------------------------------


async def test_tool_sem_token_levanta_erro_amigavel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_token", "", raising=False)
    with pytest.raises(FiscalError) as exc_info:
        await consultar_cpf_tool(CPF_TESTE)
    assert "CPFCNPJ_TOKEN" in str(exc_info.value)


async def test_tool_dv_invalido_nao_chama_provedor(provedor_habilitado: None) -> None:
    _FakeHTTPClient.ultimo_path = None
    with pytest.raises(ValueError, match="CPF inválido"):
        await consultar_cpf_tool("12345678900")
    assert _FakeHTTPClient.ultimo_path is None


async def test_tool_erro_102_cpf_inexistente(provedor_habilitado: None) -> None:
    _FakeHTTPClient.payload = {
        "status": 0,
        "cpf": "",
        "erro": "O CPF informado não existe",
        "erroCodigo": 102,
    }
    with pytest.raises(FiscalError) as exc_info:
        await consultar_cpf_tool(CPF_TESTE)
    assert "nao consta na base" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Mapeamento de situacoes e apto_emissao
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("digito", "descricao", "apto"),
    [
        ("00", "Regular", True),
        ("02", "Suspensa", False),
        ("03", "Titular Falecido", False),
        ("04", "Pendente de Regularização", False),
        ("05", "Cancelada por Multiplicidade", False),
        ("08", "Nula", False),
        ("09", "Cancelada de Ofício", False),
    ],
)
def test_parse_situacoes_e_apto_emissao(digito: str, descricao: str, apto: bool) -> None:
    amostra = {"status": 1, "nome": "FULANO", "situacaoDigito": digito, "situacao": "Rotulo"}
    cadastro = CPFClient()._parse_cpfcnpj(amostra, CPF_TESTE)
    assert cadastro.situacao is not None
    assert cadastro.situacao.codigo == digito
    assert cadastro.situacao.descricao == descricao
    assert cadastro.apto_emissao is apto


def test_parse_codigo_situacao_normaliza_para_dois_digitos() -> None:
    amostra = {"status": 1, "situacaoDigito": 3, "situacao": "Cancelada"}
    cadastro = CPFClient()._parse_cpfcnpj(amostra, CPF_TESTE)
    assert cadastro.situacao is not None
    assert cadastro.situacao.codigo == "03"
    assert cadastro.situacao.descricao == "Titular Falecido"


def test_apto_emissao_deriva_do_texto_regular_sem_digito() -> None:
    # Provedor devolve o rotulo textual sem situacaoDigito: "Regular" -> apto.
    amostra = {"status": 1, "nome": "FULANO", "situacao": "Regular"}
    cadastro = CPFClient()._parse_cpfcnpj(amostra, CPF_TESTE)
    assert cadastro.situacao is not None
    assert cadastro.situacao.codigo is None
    assert cadastro.apto_emissao is True


def test_apto_emissao_deriva_do_texto_cancelada_sem_digito() -> None:
    # Rotulo conhecido de irregularidade sem codigo -> nao apto.
    amostra = {"status": 1, "nome": "FULANO", "situacao": "Cancelada"}
    cadastro = CPFClient()._parse_cpfcnpj(amostra, CPF_TESTE)
    assert cadastro.situacao is not None
    assert cadastro.situacao.codigo is None
    assert cadastro.apto_emissao is False


def test_apto_emissao_indeterminado_sem_codigo_nem_texto() -> None:
    # Sem codigo e sem rotulo de situacao, o sinal e indeterminado (None).
    amostra = {"status": 1, "nome": "FULANO", "nascimento": "01/01/1990"}
    cadastro = CPFClient()._parse_cpfcnpj(amostra, CPF_TESTE)
    assert cadastro.situacao is None
    assert cadastro.apto_emissao is None


def test_apto_emissao_texto_desconhecido_nao_vira_true() -> None:
    # Texto fora da tabela nao autoriza apto=True: fica indeterminado (None).
    amostra = {"status": 1, "nome": "FULANO", "situacao": "Situacao Incomum"}
    cadastro = CPFClient()._parse_cpfcnpj(amostra, CPF_TESTE)
    assert cadastro.situacao is not None
    assert cadastro.situacao.codigo is None
    assert cadastro.apto_emissao is None


# ---------------------------------------------------------------------------
# Privacidade
# ---------------------------------------------------------------------------


async def test_privacidade_log_nao_contem_cpf_nem_pdf(
    provedor_habilitado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_cpf_packet", 8, raising=False)
    _FakeHTTPClient.payload = CPF_8_SAMPLE
    recorder = _RecordingLogger()
    monkeypatch.setattr(cpf_client, "logger", recorder)

    await CPFClient().consultar(CPF_TESTE)

    assert recorder.eventos, "esperava ao menos um evento de log"
    for _evento, kwargs in recorder.eventos:
        serial = repr(kwargs)
        assert CPF_TESTE not in serial
        assert "JVBERi0xLjQKJVBERg==" not in serial
    # O campo cpf logado deve estar mascarado.
    cpf_logado = recorder.eventos[0][1].get("cpf")
    assert cpf_logado == "***.***.***-35"


def test_resposta_nao_expoe_campos_operacionais() -> None:
    cadastro = CPFClient()._parse_cpfcnpj(CPF_8_SAMPLE, CPF_TESTE)
    dump = cadastro.model_dump(mode="json", exclude_none=True)
    for chave in ("saldo", "consultaID", "pacoteUsado", "delay"):
        assert chave not in dump


# ---------------------------------------------------------------------------
# API REST
# ---------------------------------------------------------------------------


_api_client = TestClient(app)


def test_api_cpf_cadastro_rejeita_dv_invalido() -> None:
    # CPF no corpo JSON (nunca no path): evita vazar o numero em access log/trace/proxy.
    response = _api_client.post("/v1/cpf/cadastro", json={"cpf": "12345678900"})
    assert response.status_code == 400
    assert response.json()["detail"] == "CPF inválido"


def test_api_cpf_cadastro_nao_expoe_cpf_no_path() -> None:
    # A rota antiga com o CPF no path deixou de existir (transporte por corpo JSON).
    response = _api_client.get(f"/v1/cpf/{CPF_TESTE}/cadastro")
    assert response.status_code == 404


def test_api_cpf_cadastro_sucesso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_token", "token_de_teste", raising=False)
    monkeypatch.setattr(settings, "cpfcnpj_cpf_packet", 26, raising=False)
    monkeypatch.setattr(cpfcnpj_provider, "HTTPClient", _FakeHTTPClient)
    _FakeHTTPClient.payload = CPF_26_SAMPLE

    response = _api_client.post("/v1/cpf/cadastro", json={"cpf": CPF_TESTE})
    assert response.status_code == 200
    data = response.json()
    assert data["cpf"] == "***.***.***-35"
    assert data["situacao"]["descricao"] == "Regular"
    assert data["apto_emissao"] is True
    assert "saldo" not in data


def test_api_cpf_cadastro_sem_token_responde_502(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_token", "", raising=False)
    response = _api_client.post("/v1/cpf/cadastro", json={"cpf": CPF_TESTE})
    assert response.status_code == 502
    assert "CPFCNPJ_TOKEN" in response.json()["detail"]


# ---------------------------------------------------------------------------
# SDK
# ---------------------------------------------------------------------------


async def test_sdk_consultar_cpf(provedor_habilitado: None) -> None:
    _FakeHTTPClient.payload = CPF_26_SAMPLE
    cadastro = await FiscalBrasil().consultar_cpf(CPF_TESTE)
    assert cadastro.apto_emissao is True
    assert cadastro.cpf == "***.***.***-35"


async def test_sdk_consultar_cpf_dv_invalido() -> None:
    with pytest.raises(ValueError, match="CPF inválido"):
        await FiscalBrasil().consultar_cpf("12345678900")


def test_sdk_consultar_cpf_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_token", "token_de_teste", raising=False)
    monkeypatch.setattr(settings, "cpfcnpj_cpf_packet", 26, raising=False)
    monkeypatch.setattr(cpfcnpj_provider, "HTTPClient", _FakeHTTPClient)
    _FakeHTTPClient.payload = CPF_26_SAMPLE
    cadastro = FiscalBrasil().consultar_cpf_sync(CPF_TESTE)
    assert cadastro.situacao is not None
    assert cadastro.situacao.codigo == "00"
