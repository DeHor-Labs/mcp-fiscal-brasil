"""Testes para nfe/_soap_mtls.py: carregamento de certificado e validacao de emitente."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from mcp_fiscal_brasil._core.config import settings as mtls_settings
from mcp_fiscal_brasil._core.errors import (
    FiscalConfigurationError,
    FiscalValidationError,
)
from mcp_fiscal_brasil.nfe._soap_mtls import (
    carregar_pkcs12,
    criar_ssl_context_em_memoria,
)


@pytest.fixture(scope="module")
def chave_privada() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def certificado(chave_privada: rsa.RSAPrivateKey) -> x509.Certificate:
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
        .public_key(chave_privada.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(chave_privada, hashes.SHA256())
    )


@pytest.fixture(scope="module")
def arquivo_pfx(
    chave_privada: rsa.RSAPrivateKey,
    certificado: x509.Certificate,
    tmp_path_factory: pytest.TempPathFactory,
) -> str:
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        b"cert_teste_mtls",
        chave_privada,
        certificado,
        None,
        serialization.BestAvailableEncryption(b"senha_teste"),
    )
    tmp_dir = tmp_path_factory.mktemp("certs_mtls")
    pfx_path = str(tmp_dir / "cert_teste.pfx")
    with open(pfx_path, "wb") as f:
        f.write(pfx_bytes)
    return pfx_path


class TestCarregarPkcs12:
    def test_caminho_inexistente_levanta_validation_error(self) -> None:
        with pytest.raises(FiscalValidationError):
            carregar_pkcs12("/caminho/que/nao/existe.pfx", "qualquer")

    def test_senha_incorreta_levanta_validation_error(self, arquivo_pfx: str) -> None:
        with pytest.raises(FiscalValidationError):
            carregar_pkcs12(arquivo_pfx, "senha_errada")

    def test_carrega_certificado_valido(self, arquivo_pfx: str) -> None:
        chave_pem, cert_pem, chain_pem = carregar_pkcs12(arquivo_pfx, "senha_teste")
        assert chave_pem.startswith(b"-----BEGIN")
        assert cert_pem.startswith(b"-----BEGIN")
        assert chain_pem == []

    def test_monta_ssl_context_sem_erro(self, arquivo_pfx: str) -> None:
        chave_pem, cert_pem, chain_pem = carregar_pkcs12(arquivo_pfx, "senha_teste")
        ctx = criar_ssl_context_em_memoria(chave_pem, cert_pem, chain_pem)
        assert ctx.verify_mode.name == "CERT_REQUIRED"


class TestValidarEmitenteCnpj:
    def test_sem_nfe_emitente_cnpj_configurado_nao_valida(
        self, arquivo_pfx: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Comportamento legado: sem NFE_EMITENTE_CNPJ, qualquer certificado carrega."""
        monkeypatch.setattr(mtls_settings, "nfe_emitente_cnpj", "")
        chave_pem, cert_pem, _ = carregar_pkcs12(arquivo_pfx, "senha_teste")
        assert chave_pem and cert_pem

    def test_cnpj_esperado_igual_ao_do_certificado_carrega_normalmente(
        self, arquivo_pfx: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mtls_settings, "nfe_emitente_cnpj", "12345678000195")
        chave_pem, cert_pem, _ = carregar_pkcs12(arquivo_pfx, "senha_teste")
        assert chave_pem and cert_pem

    def test_cnpj_esperado_formatado_com_pontuacao_tambem_funciona(
        self, arquivo_pfx: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mtls_settings, "nfe_emitente_cnpj", "12.345.678/0001-95")
        chave_pem, cert_pem, _ = carregar_pkcs12(arquivo_pfx, "senha_teste")
        assert chave_pem and cert_pem

    def test_cnpj_esperado_divergente_levanta_configuration_error(
        self, arquivo_pfx: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mtls_settings, "nfe_emitente_cnpj", "99999999000199")
        with pytest.raises(FiscalConfigurationError):
            carregar_pkcs12(arquivo_pfx, "senha_teste")
