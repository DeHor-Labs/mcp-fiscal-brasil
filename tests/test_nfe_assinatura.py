"""Testes para validacao de assinatura digital XMLDSig em NF-e."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner

from mcp_fiscal_brasil.nfe.assinatura import AssinaturaResult, validar_assinatura_nfe

_NS_NFE = "http://www.portalfiscal.inf.br/nfe"

# ID de referencia usado nos XMLs de teste
_NFE_ID = "NFe35230112345678000195550010000000011000000014"


# ---------------------------------------------------------------------------
# Fixtures de chave/cert
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chave_ca() -> rsa.RSAPrivateKey:
    """Chave RSA da CA raiz para testes."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def cert_ca(chave_ca: rsa.RSAPrivateKey) -> x509.Certificate:
    """Certificado da CA raiz autoassinado com extensoes exigidas pelo signxml 4.x."""
    ca_name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AC TESTE RAIZ"),
            x509.NameAttribute(NameOID.COMMON_NAME, "AC TESTE RAIZ"),
        ]
    )
    pub_key = chave_ca.public_key()
    return (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(pub_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(pub_key), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(pub_key),
            critical=False,
        )
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("ac-teste-raiz")]),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(chave_ca, hashes.SHA256())
    )


@pytest.fixture(scope="module")
def chave_privada(chave_ca: rsa.RSAPrivateKey) -> rsa.RSAPrivateKey:
    """Chave RSA do end-entity (assinante de XML) para testes."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def certificado_autoassinado(
    chave_privada: rsa.RSAPrivateKey,
    chave_ca: rsa.RSAPrivateKey,
    cert_ca: x509.Certificate,
) -> x509.Certificate:
    """Certificado end-entity assinado pela CA de teste.

    signxml 4.x exige: BasicConstraints CA=False, SKI, AKI, SAN e KeyUsage.
    """
    ee_name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "EMPRESA TESTE LTDA"),
            x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA TESTE LTDA:12345678000195"),
        ]
    )
    pub_key = chave_privada.public_key()
    return (
        x509.CertificateBuilder()
        .subject_name(ee_name)
        .issuer_name(cert_ca.subject)
        .public_key(pub_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(pub_key), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(chave_ca.public_key()),
            critical=False,
        )
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("empresa-teste")]),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(chave_ca, hashes.SHA256())
    )


@pytest.fixture(scope="module")
def ca_pem_file(cert_ca: x509.Certificate, tmp_path_factory: pytest.TempPathFactory) -> str:
    """Salva o PEM da CA raiz em arquivo temporario para uso como ca_bundle."""
    tmp_dir = tmp_path_factory.mktemp("ca")
    path = str(tmp_dir / "ca.pem")
    with open(path, "wb") as f:
        f.write(cert_ca.public_bytes(serialization.Encoding.PEM))
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _xml_nfe_minimo() -> str:
    """Retorna um XML de NF-e minimo (sem assinatura)."""
    return (
        f'<NFe xmlns="{_NS_NFE}">'
        f'<infNFe versao="4.00" Id="{_NFE_ID}">'
        f"<ide><cUF>35</cUF><nNF>1</nNF></ide>"
        f"</infNFe>"
        f"</NFe>"
    )


def _assinar_xml(
    xml_str: str,
    key: rsa.RSAPrivateKey,
    cert: x509.Certificate,
    reference_uri: str = f"#{_NFE_ID}",
) -> bytes:
    """Assina o XML com XMLSigner e retorna os bytes assinados."""
    root = etree.fromstring(xml_str.encode())
    signer = XMLSigner()
    # Inclui somente o EE cert no XML (sem a CA) para respeitar semantica ICP-Brasil
    signed = signer.sign(root, key=key, cert=[cert], reference_uri=reference_uri)
    return etree.tostring(signed, encoding="unicode").encode("utf-8")


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


class TestValidarAssinaturaNfe:
    """Testes para a funcao validar_assinatura_nfe."""

    def test_assinatura_valida_retorna_true(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
    ) -> None:
        """XML com assinatura correta deve retornar assinatura_valida=True.

        Valida via x509_cert (cert extraido do XML) sem exigir CA bundle.
        """
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        resultado = validar_assinatura_nfe(xml_assinado)

        assert isinstance(resultado, AssinaturaResult)
        assert resultado.assinatura_valida is True
        assert resultado.motivo is None

    def test_assinatura_valida_com_ca_bundle(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
        ca_pem_file: str,
    ) -> None:
        """XML valido com ca_bundle correto deve retornar assinatura_valida=True."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        resultado = validar_assinatura_nfe(xml_assinado, ca_bundle=ca_pem_file)

        assert resultado.assinatura_valida is True

    def test_assinatura_valida_extrai_cn_do_certificado(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
    ) -> None:
        """Validacao bem-sucedida deve extrair o CN do certificado."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        resultado = validar_assinatura_nfe(xml_assinado)

        assert resultado.titular is not None
        assert "EMPRESA TESTE" in resultado.titular

    def test_assinatura_valida_extrai_cnpj(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
    ) -> None:
        """Deve extrair o CNPJ de 14 digitos do CN do certificado."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        resultado = validar_assinatura_nfe(xml_assinado)

        # CN contem ":12345678000195" -> CNPJ extraido
        assert resultado.cnpj_cpf == "12345678000195"

    def test_assinatura_valida_retorna_validade_certificado(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
    ) -> None:
        """Deve retornar as datas de validade do certificado."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        resultado = validar_assinatura_nfe(xml_assinado)

        assert resultado.validade_inicio is not None
        assert resultado.validade_fim is not None
        assert isinstance(resultado.validade_inicio, datetime)
        assert isinstance(resultado.validade_fim, datetime)

    def test_xml_adulterado_retorna_invalido(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
    ) -> None:
        """XML com conteudo alterado apos assinatura deve ser rejeitado."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        # Adultera o XML trocando o numero da NF
        xml_adulterado = xml_assinado.replace(b"<nNF>1</nNF>", b"<nNF>9999</nNF>")

        resultado = validar_assinatura_nfe(xml_adulterado)

        assert resultado.assinatura_valida is False
        assert resultado.motivo is not None
        assert len(resultado.motivo) > 0

    def test_xml_sem_signature_retorna_invalido(self) -> None:
        """XML sem elemento Signature deve retornar assinatura_valida=False."""
        xml_sem_assinatura = (
            f'<NFe xmlns="{_NS_NFE}">'
            f'<infNFe versao="4.00" Id="{_NFE_ID}">'
            f"<ide><cUF>35</cUF><nNF>1</nNF></ide>"
            f"</infNFe>"
            f"</NFe>"
        )
        resultado = validar_assinatura_nfe(xml_sem_assinatura.encode())

        assert resultado.assinatura_valida is False
        assert resultado.motivo is not None
        assert "Signature" in resultado.motivo

    def test_xml_invalido_levanta_xml_parse_error(self) -> None:
        """XML malformado deve levantar XMLParseError (propagado de parse_xml)."""
        from mcp_fiscal_brasil.shared.exceptions import XMLParseError

        with pytest.raises(XMLParseError):
            validar_assinatura_nfe(b"<xml_invalido>")

    def test_aceita_str_e_bytes(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
    ) -> None:
        """Deve aceitar xml_content como str ou bytes."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)

        resultado_bytes = validar_assinatura_nfe(xml_assinado)
        resultado_str = validar_assinatura_nfe(xml_assinado.decode("utf-8"))

        assert resultado_bytes.assinatura_valida == resultado_str.assinatura_valida

    def test_ca_bundle_errado_retorna_invalido(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Ca_bundle com CA diferente do emissor deve retornar invalido."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        # Gera uma CA diferente (nao assinou o cert EE)
        outra_ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        outra_ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OUTRA CA")])
        outra_ca_pub = outra_ca_key.public_key()
        outra_ca_cert = (
            x509.CertificateBuilder()
            .subject_name(outra_ca_name)
            .issuer_name(outra_ca_name)
            .public_key(outra_ca_pub)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(outra_ca_pub), critical=False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(outra_ca_pub), critical=False
            )
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("outra-ca")]), critical=False)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(outra_ca_key, hashes.SHA256())
        )
        # Salva em arquivo temp

        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            f.write(outra_ca_cert.public_bytes(serialization.Encoding.PEM))
            ca_errado_path = f.name
        try:
            resultado = validar_assinatura_nfe(xml_assinado, ca_bundle=ca_errado_path)
        finally:
            os.unlink(ca_errado_path)

        assert resultado.assinatura_valida is False
        assert resultado.motivo is not None

    def test_sem_ca_bundle_valida_integridade(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
    ) -> None:
        """Sem ca_bundle, deve validar integridade via cert embutido no XML."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        # Sem ca_bundle: cert autoassinado (EE) deve passar verificacao criptografica
        resultado = validar_assinatura_nfe(xml_assinado, ca_bundle=None)

        assert resultado.assinatura_valida is True

    def test_retorna_ac_emissora(
        self,
        chave_privada: rsa.RSAPrivateKey,
        certificado_autoassinado: x509.Certificate,
    ) -> None:
        """Deve retornar informacoes da AC emissora do certificado."""
        xml_assinado = _assinar_xml(_xml_nfe_minimo(), chave_privada, certificado_autoassinado)
        resultado = validar_assinatura_nfe(xml_assinado)

        # Retorna o DN do issuer do EE cert (que eh a CA de teste)
        assert resultado.ac_emissora is not None
        assert "AC TESTE RAIZ" in resultado.ac_emissora

    def test_xml_sem_cert_embutido_e_sem_ca_bundle_retorna_invalido(self) -> None:
        """XML assinado sem X509Certificate embutido e sem ca_bundle deve retornar
        assinatura_valida=False com motivo explicativo, nunca confiar na CA store do sistema."""
        # Monta XML com Signature mas sem o elemento X509Certificate
        xml_sem_cert = (
            f'<NFe xmlns="{_NS_NFE}">'
            f'<infNFe versao="4.00" Id="{_NFE_ID}">'
            f"<ide><cUF>35</cUF><nNF>1</nNF></ide>"
            f"</infNFe>"
            f'<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'
            f"<SignedInfo/>"
            f"<SignatureValue>AAAA</SignatureValue>"
            f"</Signature>"
            f"</NFe>"
        )
        resultado = validar_assinatura_nfe(xml_sem_cert.encode())

        assert resultado.assinatura_valida is False
        assert resultado.motivo is not None
        assert "certificado" in resultado.motivo.lower() or "ca_bundle" in resultado.motivo.lower()

    def test_ca_bundle_maior_que_1mb_levanta_erro(self) -> None:
        """ca_bundle com mais de 1 MB deve levantar FiscalValidationError antes de processar."""
        from mcp_fiscal_brasil._core.errors import FiscalValidationError

        ca_bundle_gigante = b"A" * (1024 * 1024 + 1)
        with pytest.raises(FiscalValidationError, match="1 MB"):
            validar_assinatura_nfe(b"<NFe/>", ca_bundle=ca_bundle_gigante)
