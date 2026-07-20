"""Testes para o modulo NFe."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from mcp_fiscal_brasil._core.config import settings as nfe_settings
from mcp_fiscal_brasil._core.errors import FiscalConfigurationError
from mcp_fiscal_brasil.nfe.client import NFEClient, _extrair_info_chave
from mcp_fiscal_brasil.nfe.status_sefaz import _obter_ssl_context
from mcp_fiscal_brasil.nfe.tools import (
    consultar_nfe,
    consultar_status_sefaz,
    validar_chave_nfe,
)
from mcp_fiscal_brasil.shared.exceptions import (
    APIError,
    RateLimitError,
    ValidationError,
)

_NS_NFE = "http://www.portalfiscal.inf.br/nfe"


class TestValidarChaveNFe:
    async def test_chave_tamanho_errado(self) -> None:
        resultado = await validar_chave_nfe("12345")
        assert resultado["válido"] is False

    async def test_chave_com_espacos_aceita(self) -> None:
        # Espacos devem ser removidos antes da validação
        resultado = await validar_chave_nfe("1234 5678 9012")
        assert resultado["válido"] is False  # ainda invalida por tamanho

    async def test_chave_valida_extrai_campos(self) -> None:
        # Gera uma chave válida para teste
        # cUF=35 AAMM=2301 CNPJ=12345678901234 mod=55 serie=001 nNF=000000001 tpEmis=1 cNF=00000001
        # DV calculado via modulo 11
        base = "3523011234567890123455001000000001100000001"
        assert len(base) == 43

        # Calcula DV conforme algoritmo SEFAZ (modulo 11, pesos de 2 a 9 da direita p/ esquerda)
        pesos_ciclo = list(range(2, 10))
        soma = sum(int(d) * pesos_ciclo[i % len(pesos_ciclo)] for i, d in enumerate(reversed(base)))
        resto = soma % 11
        dv = 0 if resto in (0, 1) else 11 - resto
        chave = base + str(dv)

        resultado = await validar_chave_nfe(chave)
        assert resultado["válido"] is True
        assert resultado["uf"] == "SP"
        assert resultado["cnpj_emitente"] == "12345678901234"


def _gerar_pfx_teste(tmp_path_factory: pytest.TempPathFactory) -> str:
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA TESTE:12345678000195"),
        ]
    )
    certificado = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(chave, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        b"cert_teste_nfe",
        chave,
        certificado,
        None,
        serialization.BestAvailableEncryption(b"senha_teste"),
    )
    tmp_dir = tmp_path_factory.mktemp("certs_nfe_tools")
    pfx_path = str(tmp_dir / "cert_teste.pfx")
    with open(pfx_path, "wb") as f:
        f.write(pfx_bytes)
    return pfx_path


def _montar_ret_stat_serv_operacional() -> etree._Element:
    body_str = (
        f'<retConsStatServ versao="4.00" xmlns="{_NS_NFE}">'
        "<tpAmb>1</tpAmb>"
        "<cStat>107</cStat>"
        "<xMotivo>Servico em Operacao</xMotivo>"
        "<cUF>35</cUF>"
        "<dhRecbto>2026-07-18T10:00:00-03:00</dhRecbto>"
        "<tMed>1</tMed>"
        "</retConsStatServ>"
    )
    return etree.fromstring(body_str.encode())


class TestConsultarStatusSEFAZ:
    async def test_uf_invalida_levanta_erro(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await consultar_status_sefaz("XX")
        assert exc_info.value.field == "uf"

    async def test_sem_certificado_levanta_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(nfe_settings, "nfe_certificado_path", "")
        monkeypatch.setattr(nfe_settings, "nfe_certificado_senha", "")

        with pytest.raises(FiscalConfigurationError):
            await consultar_status_sefaz("SP")

    async def test_uf_valida_com_certificado_retorna_status(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        pfx_path = _gerar_pfx_teste(tmp_path_factory)
        monkeypatch.setattr(nfe_settings, "nfe_certificado_path", pfx_path)
        monkeypatch.setattr(nfe_settings, "nfe_certificado_senha", "senha_teste")

        body_mock = _montar_ret_stat_serv_operacional()
        _obter_ssl_context.cache_clear()
        with patch(
            "mcp_fiscal_brasil.nfe.status_sefaz._enviar_soap_mtls",
            new=AsyncMock(return_value=body_mock),
        ):
            resultado = await consultar_status_sefaz("SP")

        assert resultado.uf == "SP"
        assert resultado.status == "OPERACIONAL"
        assert resultado.código == 107


def _chave_valida_sp() -> str:
    """Gera uma chave de acesso válida para SP (cUF=35)."""
    base = "3523011234567890123455001000000001100000001"
    assert len(base) == 43
    pesos_ciclo = list(range(2, 10))
    soma = sum(int(d) * pesos_ciclo[i % len(pesos_ciclo)] for i, d in enumerate(reversed(base)))
    resto = soma % 11
    dv = 0 if resto in (0, 1) else 11 - resto
    return base + str(dv)


class TestExtrairInfoChave:
    def test_extrai_uf_cnpj_numero(self) -> None:
        chave = _chave_valida_sp()
        info = _extrair_info_chave(chave)
        assert info["uf"] == "SP"
        assert info["cnpj_emitente"] == "12345678901234"
        assert info["número"] == "000000001"
        assert info["serie"] == "001"
        assert info["modelo"] == "55"


class TestNFEClientFallback:
    """Testa a cadeia de fallback do NFEClient sem realizar chamadas HTTP reais."""

    async def test_brasil_api_sucesso_nao_chama_portal(self) -> None:
        chave = _chave_valida_sp()
        client = NFEClient()

        from mcp_fiscal_brasil.nfe.schemas import NFeResponse

        mock_resp = NFeResponse(chave_acesso=chave, número="1", serie="1", situacao="Autorizada")

        with patch.object(client, "_consultar_brasil_api", new=AsyncMock(return_value=mock_resp)):
            with patch.object(client, "_consultar_portal_nfe", new=AsyncMock()) as portal_mock:
                resultado = await client.consultar_por_chave(chave)

        assert resultado.situacao == "Autorizada"
        portal_mock.assert_not_called()

    async def test_brasil_api_rate_limit_cai_no_portal(self) -> None:
        chave = _chave_valida_sp()
        client = NFEClient()

        from mcp_fiscal_brasil.nfe.schemas import NFeResponse

        mock_resp = NFeResponse(chave_acesso=chave, número="1", serie="1", situacao="Autorizada")

        with patch.object(
            client,
            "_consultar_brasil_api",
            new=AsyncMock(side_effect=RateLimitError(endpoint="brasilapi/nfe")),
        ):
            with patch.object(
                client, "_consultar_portal_nfe", new=AsyncMock(return_value=mock_resp)
            ) as portal_mock:
                resultado = await client.consultar_por_chave(chave)

        portal_mock.assert_called_once_with(chave)
        assert resultado.situacao == "Autorizada"

    async def test_brasil_api_erro_cai_no_portal(self) -> None:
        chave = _chave_valida_sp()
        client = NFEClient()

        from mcp_fiscal_brasil.nfe.schemas import NFeResponse

        mock_resp = NFeResponse(chave_acesso=chave, número="1", serie="1", situacao="Autorizada")

        with patch.object(
            client,
            "_consultar_brasil_api",
            new=AsyncMock(side_effect=APIError(message="não encontrado", status_code=404)),
        ):
            with patch.object(
                client, "_consultar_portal_nfe", new=AsyncMock(return_value=mock_resp)
            ):
                resultado = await client.consultar_por_chave(chave)

        assert resultado.situacao == "Autorizada"

    async def test_todas_apis_falham_retorna_parcial(self) -> None:
        chave = _chave_valida_sp()
        client = NFEClient()

        with patch.object(
            client,
            "_consultar_brasil_api",
            new=AsyncMock(side_effect=APIError(message="indisponivel", status_code=503)),
        ):
            with patch.object(
                client,
                "_consultar_portal_nfe",
                new=AsyncMock(side_effect=APIError(message="indisponivel", status_code=503)),
            ):
                resultado = await client.consultar_por_chave(chave)

        assert resultado.chave_acesso == chave
        assert resultado.emitente is not None
        assert resultado.emitente.cnpj == "12345678901234"
        assert "parciais" in (resultado.situacao or "").lower()
        assert resultado.informacoes_adicionais is not None
        assert "SP" in resultado.informacoes_adicionais

    async def test_chave_invalida_levanta_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await consultar_nfe("1234567890")
        assert exc_info.value.field == "chave_acesso"
