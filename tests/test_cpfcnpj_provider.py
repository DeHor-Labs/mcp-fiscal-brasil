"""Testes do provedor premium opcional cpfcnpj.com.br.

Cobrem o transporte (status de sucesso/erro e ausencia de token), o mapeamento
das respostas de CNPJ (pacote 6) e de NF-e/NFC-e por chave (pacotes 100/102) e a
garantia de que, sem token configurado, o comportamento gratuito padrao nao muda.
"""

import asyncio
import time
from itertools import pairwise
from typing import Any, ClassVar

import httpx
import pytest

from mcp_fiscal_brasil._core import FiscalHTTPError, settings
from mcp_fiscal_brasil._core.http import HTTPClient
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


async def test_erro_provedor_nao_expoe_documento(provedor_habilitado: None) -> None:
    # A url da excecao viaja para access log/trace/proxy: o documento consultado nao
    # pode vazar. Mascarado como .../***/{pacote}/*** (token e documento ocultos).
    documento = "11144477735"
    _FakeHTTPClient.payload = {"status": 0, "erro": "Consulta sem sucesso.", "erroCodigo": 300}
    with pytest.raises(FiscalHTTPError) as exc_info:
        await cpfcnpj_provider.consultar(26, documento)
    erro = exc_info.value
    assert documento not in str(erro)
    assert documento not in repr(erro)
    assert documento not in str(erro.url)
    assert documento not in str(erro.detail)
    assert erro.url.endswith("/***/26/***")


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
    # O mesmo grupo de req/s devolve sempre o mesmo limitador de processo (singleton
    # de modulo). Pacotes 6 e 26 sao do mesmo grupo (20 req/s), entao os clientes
    # abertos para eles compartilham o limitador.
    limitador = cpfcnpj_provider._get_limiter(6)
    assert limitador is cpfcnpj_provider._get_limiter(6)
    cliente_a = cpfcnpj_provider._http_client(6)
    cliente_b = cpfcnpj_provider._http_client(26)
    assert cliente_a._limiter is cliente_b._limiter
    assert cliente_a._limiter is limitador


def test_limitador_cpfcnpj_compartilhado_entre_event_loops() -> None:
    # O limitador e por processo, nao por loop: dois asyncio.run consecutivos (como
    # consultar_cpf_sync/consultar_cnpj_sync do SDK, que abrem um loop novo a cada
    # chamada) recebem o MESMO objeto para o mesmo grupo. Grupos distintos (padrao x
    # NF-e) permanecem separados em qualquer loop.
    async def _limitadores() -> tuple[Any, Any, Any]:
        return (
            cpfcnpj_provider._get_limiter(6),
            cpfcnpj_provider._get_limiter(26),
            cpfcnpj_provider._get_limiter(100),
        )

    a_padrao, a_padrao_26, a_nfe = asyncio.run(_limitadores())
    b_padrao, _b_padrao_26, b_nfe = asyncio.run(_limitadores())

    # Mesmo grupo -> mesmo objeto, dentro do loop e entre loops distintos.
    assert a_padrao is a_padrao_26
    assert a_padrao is b_padrao
    assert a_nfe is b_nfe
    # Grupos distintos (20 req/s x 2 req/s) -> objetos distintos.
    assert a_padrao is not a_nfe


def test_limitador_orcamento_compartilhado_entre_event_loops() -> None:
    # O orcamento e dividido entre loops: com 2 req/s, tres acquires espalhados por
    # dois asyncio.run consecutivos precisam esperar a janela liberar, gastando tempo
    # real. Dois acquires no mesmo segundo cabem na janela e nao esperam.
    limitador = cpfcnpj_provider._LimitadorDeProcesso(2)

    async def _dois_acquires() -> None:
        await limitador.acquire()
        await limitador.acquire()

    async def _um_acquire() -> None:
        await limitador.acquire()

    inicio = time.monotonic()
    asyncio.run(_dois_acquires())
    sem_espera = time.monotonic() - inicio
    asyncio.run(_um_acquire())
    total = time.monotonic() - inicio

    # Os dois primeiros (mesma janela de 1 s) nao esperam.
    assert sem_espera < 0.3
    # O terceiro estoura a janela e espera ate a vaga liberar (tolerancia ampla).
    assert total >= 0.5


def test_limitador_thread_safe_basico() -> None:
    # Chamadas concorrentes de threads distintas nao corrompem o agendamento interno:
    # com 2 req/s e 6 acquires, restam no maximo `taxa` vagas ativas na janela.
    import threading

    limitador = cpfcnpj_provider._LimitadorDeProcesso(2, janela=0.01)

    def _bate() -> None:
        asyncio.run(limitador.acquire())

    threads = [threading.Thread(target=_bate) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(limitador._agendadas) <= limitador.taxa


def test_limitador_nfe_separado_dos_demais() -> None:
    # Pacotes 100/102 (NF-e/NFC-e) compartilham um limitador de 2 req/s entre si,
    # distinto do limitador de 20 req/s usado por CPF/CNPJ (6, 26).
    limitador_nfe = cpfcnpj_provider._get_limiter(100)
    assert limitador_nfe is cpfcnpj_provider._get_limiter(102)
    assert limitador_nfe is not cpfcnpj_provider._get_limiter(6)
    assert cpfcnpj_provider._rate_limit_para(100) == 2
    assert cpfcnpj_provider._rate_limit_para(102) == 2
    assert cpfcnpj_provider._rate_limit_para(6) == 20
    assert cpfcnpj_provider._rate_limit_para(26) == 20
    cliente_nfe = cpfcnpj_provider._http_client(100)
    assert cliente_nfe.rate_limit_per_second == 2
    assert cpfcnpj_provider._http_client(6).rate_limit_per_second == 20


def test_http_client_usa_timeout_do_provedor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cpfcnpj_timeout", 60.0, raising=False)
    assert cpfcnpj_provider._http_client(6).timeout == 60.0
    assert cpfcnpj_provider._http_client(6).mask_first_path_segment is True


def test_http_client_passa_token_como_mask_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # O token e passado como segredo literal: defesa em profundidade para bases
    # com prefixo de path, removendo-o mesmo fora do formato esperado de URL.
    monkeypatch.setattr(settings, "cpfcnpj_token", "token_de_teste", raising=False)
    assert cpfcnpj_provider._http_client(6).mask_secret == "token_de_teste"


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


_TOKEN_SECRETO = "SEGREDO_TOKEN_12345"
_URL_COM_TOKEN = f"https://api.cpfcnpj.com.br/{_TOKEN_SECRETO}/26/11144477735"


def _sem_token(erro: Exception) -> None:
    assert _TOKEN_SECRETO not in str(erro)
    assert _TOKEN_SECRETO not in repr(erro)
    assert _TOKEN_SECRETO not in str(getattr(erro, "url", ""))
    assert _TOKEN_SECRETO not in str(getattr(erro, "endpoint", ""))
    assert _TOKEN_SECRETO not in str(getattr(erro, "detail", ""))
    assert "***" in str(getattr(erro, "url", ""))


def test_http_error_mascara_token_no_path() -> None:
    cliente = HTTPClient("https://api.cpfcnpj.com.br", mask_first_path_segment=True)
    requisicao = httpx.Request("GET", _URL_COM_TOKEN)
    resposta = httpx.Response(400, request=requisicao, text='{"status":0,"erroCodigo":100}')
    erro = cliente._http_error("GET", resposta)
    _sem_token(erro)


def test_request_error_mascara_token_no_path() -> None:
    cliente = HTTPClient("https://api.cpfcnpj.com.br", mask_first_path_segment=True)
    requisicao = httpx.Request("GET", _URL_COM_TOKEN)
    exc = httpx.ConnectError(f"falha ao conectar em {_URL_COM_TOKEN}", request=requisicao)
    erro = cliente._request_error("GET", exc)
    _sem_token(erro)


def test_fontes_gratuitas_nao_mascaram_path() -> None:
    # Sem o flag, o path das fontes gratuitas continua intacto (nao ha segredo la).
    cliente = HTTPClient("https://brasilapi.com.br/api")
    url = "https://brasilapi.com.br/api/cnpj/v1/00000000000191"
    requisicao = httpx.Request("GET", url)
    resposta = httpx.Response(404, request=requisicao, text="{}")
    erro = cliente._http_error("GET", resposta)
    assert "00000000000191" in str(getattr(erro, "url", ""))


# Base com prefixo de path (documentada no README: CPFCNPJ_BASE_URL=https://proxy/cpfcnpj).
_URL_PREFIXO_COM_TOKEN = f"https://proxy.exemplo/cpfcnpj/{_TOKEN_SECRETO}/26/11144477735"


def test_http_error_mascara_token_com_base_url_prefixada() -> None:
    # Com prefixo de path, o token vem DEPOIS do prefixo: o mascaramento deve
    # trocar o token, nao o segmento "cpfcnpj" do prefixo. Sem mask_secret aqui,
    # provando que a logica ciente do prefixo ja resolve o vazamento.
    cliente = HTTPClient("https://proxy.exemplo/cpfcnpj", mask_first_path_segment=True)
    requisicao = httpx.Request("GET", _URL_PREFIXO_COM_TOKEN)
    resposta = httpx.Response(400, request=requisicao, text='{"status":0,"erroCodigo":100}')
    erro = cliente._http_error("GET", resposta)
    _sem_token(erro)
    url_mascarada = str(getattr(erro, "url", ""))
    assert "cpfcnpj" in url_mascarada
    assert "/cpfcnpj/***/26/" in url_mascarada


def test_request_error_mascara_token_com_base_url_prefixada() -> None:
    # Idem para erro de rede: o token some da url, do endpoint, do detail e da mensagem.
    cliente = HTTPClient(
        "https://proxy.exemplo/cpfcnpj",
        mask_first_path_segment=True,
        mask_secret=_TOKEN_SECRETO,
    )
    requisicao = httpx.Request("GET", _URL_PREFIXO_COM_TOKEN)
    exc = httpx.ConnectError(f"falha ao conectar em {_URL_PREFIXO_COM_TOKEN}", request=requisicao)
    erro = cliente._request_error("GET", exc)
    _sem_token(erro)
    assert _TOKEN_SECRETO not in str(getattr(erro, "detail", ""))


@pytest.mark.asyncio
async def test_limitador_reavalia_janela_ao_acordar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma tarefa que acorda atrasada nao pode partir junto com outra na mesma janela.

    Relogio e sleep falsos, deterministicos: o primeiro sleep "atrasa" 0,6 s ao
    retomar (como um loop ocupado faria). Com taxa 1 e janela 1 s, a requisicao
    atrasada parte em 1,6 s; a seguinte so pode partir em 2,6 s. Se a vaga fosse
    reservada antes de dormir, sem reavaliar a janela ao acordar, a seguinte
    partiria em 2,0 s, ou seja, duas requisicoes em menos de 1 s (HTTP 429/1007).
    """
    relogio = {"agora": 0.0, "atrasos": [0.6]}

    def monotonic_falso() -> float:
        return relogio["agora"]

    async def sleep_falso(segundos: float) -> None:
        atraso = relogio["atrasos"].pop(0) if relogio["atrasos"] else 0.0
        relogio["agora"] += segundos + atraso

    monkeypatch.setattr(cpfcnpj_provider.time, "monotonic", monotonic_falso)
    monkeypatch.setattr(cpfcnpj_provider.asyncio, "sleep", sleep_falso)

    limitador = cpfcnpj_provider._LimitadorDeProcesso(1, janela=1.0)
    partidas: list[float] = []
    for _ in range(3):
        await limitador.acquire()
        partidas.append(relogio["agora"])

    assert partidas[0] == 0.0
    assert partidas[1] == pytest.approx(1.6)
    intervalos = [b - a for a, b in pairwise(partidas)]
    assert all(i >= 1.0 for i in intervalos), partidas
