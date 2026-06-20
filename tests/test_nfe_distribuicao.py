"""Testes para baixar_nfe_distribuicao e manifestar_nfe (mocks - sem SEFAZ real)."""

from __future__ import annotations

import base64
import gzip
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from mcp_fiscal_brasil._core.errors import FiscalValidationError
from mcp_fiscal_brasil.nfe.distribuicao import (
    EVENTO_CIENCIA,
    EVENTO_CONFIRMACAO,
    EVENTO_OPERACAO_NAO_REALIZADA,
    DistribuicaoResult,
    DocumentoDistribuicao,
    ManifestacaoResult,
    baixar_nfe_distribuicao,
    manifestar_nfe,
)

_NS_NFE = "http://www.portalfiscal.inf.br/nfe"

# CNPJ valido para testes (Petrobras, conforme conftest)
_CNPJ_TESTE = "33000167000101"
# Chave valida calculada: cUF=35 AAMM=2301 CNPJ=12345678901234 mod=55 serie=001 nNF=1 tpEmis=1 cNF=1
_BASE_CHAVE = "3523011234567890123455001000000001100000001"
# DV calculado via modulo 11 (pesos 2-9)
_pesos = list(range(2, 10))
_soma = sum(int(d) * _pesos[i % 8] for i, d in enumerate(reversed(_BASE_CHAVE)))
_resto = _soma % 11
_dv = 0 if _resto in (0, 1) else 11 - _resto
_CHAVE_VALIDA = _BASE_CHAVE + str(_dv)

assert len(_CHAVE_VALIDA) == 44


# ---------------------------------------------------------------------------
# Fixtures de certificado
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chave_privada_a1() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def certificado_a1(chave_privada_a1: rsa.RSAPrivateKey) -> x509.Certificate:
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA TESTE:12345678000195"),
        ]
    )
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(chave_privada_a1.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(chave_privada_a1, hashes.SHA256())
    )


@pytest.fixture(scope="module")
def arquivo_pfx(
    chave_privada_a1: rsa.RSAPrivateKey,
    certificado_a1: x509.Certificate,
    tmp_path_factory: pytest.TempPathFactory,
) -> str:
    """Cria um arquivo .pfx temporario com o certificado de teste."""
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        b"cert_teste",
        chave_privada_a1,
        certificado_a1,
        None,
        serialization.BestAvailableEncryption(b"senha_teste"),
    )
    tmp_dir = tmp_path_factory.mktemp("certs")
    pfx_path = str(tmp_dir / "cert_teste.pfx")
    with open(pfx_path, "wb") as f:
        f.write(pfx_bytes)
    return pfx_path


# ---------------------------------------------------------------------------
# Helpers para gerar XML de teste
# ---------------------------------------------------------------------------


def _gerar_doc_zip_resnfe(chave: str, c_sit_nfe: str = "100") -> str:
    """Gera um docZip base64+gzip de um resNFe minimo para testes.

    Args:
        chave: Chave de acesso de 44 digitos da NF-e.
        c_sit_nfe: Codigo de situacao da NF-e (cSitNFe). Padrao "100" = Autorizada.
    """
    xml = (
        f'<resNFe versao="1.01" xmlns="{_NS_NFE}">'
        f"<chNFe>{chave}</chNFe>"
        f"<CNPJ>12345678000195</CNPJ>"
        f"<xNome>EMPRESA TESTE LTDA</xNome>"
        f"<vNF>1000.00</vNF>"
        f"<tpNF>1</tpNF>"
        f"<cSitNFe>{c_sit_nfe}</cSitNFe>"
        f"<dhRecbto>2023-01-15T10:00:00-03:00</dhRecbto>"
        f"</resNFe>"
    )
    compressed = gzip.compress(xml.encode("utf-8"))
    return base64.b64encode(compressed).decode("ascii")


def _montar_retorno_dist_soap(
    ultimo_nsu: str = "000000000000001",
    max_nsu: str = "000000000000001",
    docs: list[tuple[str, str, str]] | None = None,
    c_stat: str = "138",
    x_motivo: str = "Documento localizado",
) -> etree._Element:
    """Monta um elemento XML simulando o Body SOAP de retDistDFeInt."""
    docs_xml = ""
    if docs:
        for nsu, schema, doc_zip in docs:
            docs_xml += f'<docZip NSU="{nsu}" schema="{schema}">{doc_zip}</docZip>'

    lote = f"<loteDistDFeInt>{docs_xml}</loteDistDFeInt>" if docs_xml else ""

    body_str = (
        f'<retDistDFeInt versao="1.01" xmlns="{_NS_NFE}">'
        f"<tpAmb>1</tpAmb>"
        f"<verAplic>1.3.0</verAplic>"
        f"<cStat>{c_stat}</cStat>"
        f"<xMotivo>{x_motivo}</xMotivo>"
        f"<dhResp>2023-01-15T10:00:00-03:00</dhResp>"
        f"<ultNSU>{ultimo_nsu}</ultNSU>"
        f"<maxNSU>{max_nsu}</maxNSU>"
        f"{lote}"
        f"</retDistDFeInt>"
    )
    return etree.fromstring(body_str.encode())


def _montar_retorno_evento_soap(
    c_stat: str = "135",
    x_motivo: str = "Evento registrado e vinculado a NF-e",
    n_prot: str = "999000000000001",
) -> etree._Element:
    """Monta um elemento XML simulando o Body SOAP de retEnvEvento."""
    body_str = (
        f'<retEnvEvento versao="1.00" xmlns="{_NS_NFE}">'
        f"<idLote>1</idLote>"
        f"<tpAmb>1</tpAmb>"
        f"<verAplic>1.0</verAplic>"
        f"<cOrgao>91</cOrgao>"
        f"<cStat>{c_stat}</cStat>"
        f"<xMotivo>{x_motivo}</xMotivo>"
        f'<retEvento versao="1.00">'
        f"<infEvento>"
        f"<cOrgao>91</cOrgao>"
        f"<cStat>{c_stat}</cStat>"
        f"<xMotivo>{x_motivo}</xMotivo>"
        f"<nProt>{n_prot}</nProt>"
        f"</infEvento>"
        f"</retEvento>"
        f"</retEnvEvento>"
    )
    return etree.fromstring(body_str.encode())


# ---------------------------------------------------------------------------
# Testes de baixar_nfe_distribuicao
# ---------------------------------------------------------------------------


class TestBaixarNfeDistribuicao:
    """Testes para baixar_nfe_distribuicao com mocks de HTTP."""

    async def test_modo_dist_nsu_retorna_documentos(self, arquivo_pfx: str) -> None:
        """Modo distNSU deve retornar DistribuicaoResult com documentos."""
        doc_zip = _gerar_doc_zip_resnfe(_CHAVE_VALIDA)
        body_mock = _montar_retorno_dist_soap(
            docs=[("000000000000001", "resNFe_v1.01.xsd", doc_zip)],
        )

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ):
            resultado = await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                uf="SP",
                modo="distNSU",
                ultimo_nsu="0",
            )

        assert isinstance(resultado, DistribuicaoResult)
        assert resultado.ultimo_nsu == "000000000000001"
        assert len(resultado.documentos) == 1

    async def test_modo_dist_nsu_documento_resnfe(self, arquivo_pfx: str) -> None:
        """O documento retornado no modo distNSU deve ter tipo resNFe."""
        doc_zip = _gerar_doc_zip_resnfe(_CHAVE_VALIDA)
        body_mock = _montar_retorno_dist_soap(
            docs=[("000000000000001", "resNFe_v1.01.xsd", doc_zip)],
        )

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ):
            resultado = await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                uf="35",
                modo="distNSU",
            )

        doc = resultado.documentos[0]
        assert isinstance(doc, DocumentoDistribuicao)
        assert doc.tipo == "resNFe"
        assert doc.resumo is not None

    async def test_modo_cons_nsu(self, arquivo_pfx: str) -> None:
        """Modo consNSU deve passar NSU especifico na requisicao."""
        body_mock = _montar_retorno_dist_soap(
            docs=[],
            c_stat="137",
            x_motivo="Nenhum documento localizado",
        )

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ) as mock_soap:
            resultado = await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                uf="SP",
                modo="consNSU",
                nsu="42",
            )

        mock_soap.assert_called_once()
        # Verifica que o body contem consNSU
        call_args = mock_soap.call_args
        body_content = call_args[0][1]  # segundo argumento posicional
        assert "consNSU" in body_content
        assert len(resultado.documentos) == 0

    async def test_modo_cons_ch_nfe(self, arquivo_pfx: str) -> None:
        """Modo consChNFe deve passar a chave de acesso na requisicao."""
        doc_zip = _gerar_doc_zip_resnfe(_CHAVE_VALIDA)
        body_mock = _montar_retorno_dist_soap(
            docs=[("000000000000042", "resNFe_v1.01.xsd", doc_zip)],
        )

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ) as mock_soap:
            resultado = await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                uf="SP",
                modo="consChNFe",
                chave=_CHAVE_VALIDA,
            )

        call_args = mock_soap.call_args
        body_content = call_args[0][1]
        assert "consChNFe" in body_content
        assert _CHAVE_VALIDA in body_content
        assert len(resultado.documentos) == 1

    async def test_erro_sem_certificado(self) -> None:
        """Caminho de certificado inexistente deve levancar FiscalValidationError."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await baixar_nfe_distribuicao(
                caminho_certificado="/caminho/inexistente.pfx",
                senha="qualquer",
                cnpj_cpf=_CNPJ_TESTE,
                uf="SP",
            )
        assert "certificado" in exc_info.value.message.lower()

    async def test_erro_senha_incorreta(self, arquivo_pfx: str) -> None:
        """Senha errada deve levancar FiscalValidationError sem vazar a senha."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_errada",
                cnpj_cpf=_CNPJ_TESTE,
                uf="SP",
            )
        # A senha NAO deve aparecer na mensagem de erro
        assert "senha_errada" not in exc_info.value.message

    async def test_erro_cnpj_invalido(self, arquivo_pfx: str) -> None:
        """CNPJ com formato invalido deve levancar FiscalValidationError."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf="123",
                uf="SP",
            )
        assert exc_info.value.field == "cnpj_cpf"

    async def test_erro_chave_invalida_modo_cons_ch(self, arquivo_pfx: str) -> None:
        """Chave de acesso invalida no modo consChNFe deve levancar FiscalValidationError."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                uf="SP",
                modo="consChNFe",
                chave="1234567890",
            )
        assert exc_info.value.field == "chave"

    async def test_erro_modo_cons_nsu_sem_nsu(self, arquivo_pfx: str) -> None:
        """Modo consNSU sem o parametro nsu deve levancar FiscalValidationError."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                uf="SP",
                modo="consNSU",
                nsu=None,
            )
        assert exc_info.value.field == "nsu"

    async def test_parsing_chave_no_resnfe(self, arquivo_pfx: str) -> None:
        """O campo chave do documento resNFe deve ser extraido corretamente."""
        doc_zip = _gerar_doc_zip_resnfe(_CHAVE_VALIDA)
        body_mock = _montar_retorno_dist_soap(
            docs=[("000000000000001", "resNFe_v1.01.xsd", doc_zip)],
        )

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ):
            resultado = await baixar_nfe_distribuicao(
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                uf="SP",
            )

        doc = resultado.documentos[0]
        # Chave do resNFe eh os 44 digitos numericos
        assert doc.chave is not None
        assert len(doc.chave) == 44


# ---------------------------------------------------------------------------
# Testes de _extrair_resumo_resnfe (campo situacao)
# ---------------------------------------------------------------------------


def test_extrair_resumo_resnfe_usa_csitnfe() -> None:
    """situacao deve vir de cSitNFe, nao de digVal."""
    from lxml import etree as _etree

    from mcp_fiscal_brasil.nfe.distribuicao import _extrair_resumo_resnfe

    xml_com_csitnfe = (
        f'<resNFe versao="1.01" xmlns="{_NS_NFE}">'
        f"<chNFe>{'0' * 44}</chNFe>"
        f"<cSitNFe>100</cSitNFe>"
        f"<digVal>abc123</digVal>"
        f"</resNFe>"
    )
    root = _etree.fromstring(xml_com_csitnfe.encode())
    resumo = _extrair_resumo_resnfe(root)
    assert resumo["situacao"] == "100", "situacao deve ser o valor de cSitNFe"


def test_extrair_resumo_resnfe_sem_csitnfe_retorna_none() -> None:
    """Quando cSitNFe ausente, situacao deve ser None (nao digVal)."""
    from lxml import etree as _etree

    from mcp_fiscal_brasil.nfe.distribuicao import _extrair_resumo_resnfe

    xml_sem_csitnfe = (
        f'<resNFe versao="1.01" xmlns="{_NS_NFE}">'
        f"<chNFe>{'0' * 44}</chNFe>"
        f"<digVal>hash_do_documento</digVal>"
        f"</resNFe>"
    )
    root = _etree.fromstring(xml_sem_csitnfe.encode())
    resumo = _extrair_resumo_resnfe(root)
    assert resumo["situacao"] is None, "situacao deve ser None quando cSitNFe ausente"


# ---------------------------------------------------------------------------
# Testes de manifestar_nfe
# ---------------------------------------------------------------------------


class TestManifestarNfe:
    """Testes para manifestar_nfe com mocks de HTTP."""

    async def test_ciencia_sucesso(self, arquivo_pfx: str) -> None:
        """Evento 210200 (Ciencia) deve retornar ManifestacaoResult com sucesso."""
        body_mock = _montar_retorno_evento_soap()

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ):
            resultado = await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento=EVENTO_CIENCIA,
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
            )

        assert isinstance(resultado, ManifestacaoResult)
        assert resultado.sucesso is True
        assert resultado.codigo_retorno == "135"
        assert resultado.numero_protocolo == "999000000000001"

    async def test_confirmacao_sucesso(self, arquivo_pfx: str) -> None:
        """Evento 210210 (Confirmacao) deve retornar sucesso."""
        body_mock = _montar_retorno_evento_soap()

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ):
            resultado = await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento=EVENTO_CONFIRMACAO,
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
            )

        assert resultado.sucesso is True

    async def test_operacao_nao_realizada_requer_justificativa(self, arquivo_pfx: str) -> None:
        """Evento 210240 sem justificativa deve levancar FiscalValidationError."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento=EVENTO_OPERACAO_NAO_REALIZADA,
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
            )
        assert exc_info.value.field == "justificativa"

    async def test_operacao_nao_realizada_justificativa_curta(self, arquivo_pfx: str) -> None:
        """Justificativa com menos de 15 chars deve levancar FiscalValidationError."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento=EVENTO_OPERACAO_NAO_REALIZADA,
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                justificativa="curto",
            )
        assert "15" in exc_info.value.message

    async def test_operacao_nao_realizada_com_justificativa_valida(self, arquivo_pfx: str) -> None:
        """Evento 210240 com justificativa valida deve montar o XML e chamar SOAP."""
        body_mock = _montar_retorno_evento_soap()

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ) as mock_soap:
            resultado = await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento=EVENTO_OPERACAO_NAO_REALIZADA,
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
                justificativa="Produto nao foi recebido pelo destinatario",
            )

        mock_soap.assert_called_once()
        assert resultado.sucesso is True

    async def test_tipo_evento_invalido(self, arquivo_pfx: str) -> None:
        """Tipo de evento desconhecido deve levancar FiscalValidationError."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento="999999",
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
            )
        assert exc_info.value.field == "tipo_evento"

    async def test_chave_invalida_levanta_validation_error(self, arquivo_pfx: str) -> None:
        """Chave de acesso invalida deve levancar FiscalValidationError."""
        with pytest.raises(FiscalValidationError) as exc_info:
            await manifestar_nfe(
                chave="0000",
                tipo_evento=EVENTO_CIENCIA,
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
            )
        assert exc_info.value.field == "chave"

    async def test_evento_contem_chave_e_tipo(self, arquivo_pfx: str) -> None:
        """O body enviado a SEFAZ deve conter a chave e o tipo do evento."""
        body_mock = _montar_retorno_evento_soap()

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ) as mock_soap:
            await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento=EVENTO_CIENCIA,
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
            )

        call_args = mock_soap.call_args
        body_content = call_args[0][1]
        assert _CHAVE_VALIDA in body_content
        assert EVENTO_CIENCIA in body_content

    async def test_montagem_evento_assina_xml(self, arquivo_pfx: str) -> None:
        """O body deve conter um elemento Signature (evento assinado)."""
        body_mock = _montar_retorno_evento_soap()

        with patch(
            "mcp_fiscal_brasil.nfe.distribuicao._enviar_soap",
            new=AsyncMock(return_value=body_mock),
        ) as mock_soap:
            await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento=EVENTO_CIENCIA,
                caminho_certificado=arquivo_pfx,
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
            )

        call_args = mock_soap.call_args
        body_content = call_args[0][1]
        assert "Signature" in body_content

    async def test_sem_certificado_levanta_validation_error(self) -> None:
        """Certificado inexistente deve levancar FiscalValidationError antes de HTTP."""
        with pytest.raises(FiscalValidationError):
            await manifestar_nfe(
                chave=_CHAVE_VALIDA,
                tipo_evento=EVENTO_CIENCIA,
                caminho_certificado="/nao_existe.pfx",
                senha="senha_teste",
                cnpj_cpf=_CNPJ_TESTE,
            )
