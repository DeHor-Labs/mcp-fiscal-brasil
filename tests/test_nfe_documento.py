"""Testes para parse_nfe_documento (nfe/documento.py)."""

import pytest

from mcp_fiscal_brasil._core.errors import FiscalValidationError
from mcp_fiscal_brasil.nfe.documento import DocumentoParseError, parse_nfe_documento

# XML minimo de NF-e modelo 55 sem namespace, sem protocolo
XML_NFE_55_SIMPLES = """
<NFe>
  <infNFe Id="NFe35240112345678000195550010000001231000000012">
    <ide>
      <mod>55</mod>
      <serie>1</serie>
      <nNF>123</nNF>
      <dhEmi>2024-01-31T10:30:00-03:00</dhEmi>
      <natOp>Venda de mercadoria</natOp>
      <tpNF>1</tpNF>
    </ide>
    <emit>
      <CNPJ>12345678000195</CNPJ>
      <xNome>EMPRESA TESTE LTDA</xNome>
      <enderEmit>
        <xLgr>Rua Fiscal</xLgr>
        <nro>100</nro>
        <xBairro>Centro</xBairro>
        <xMun>Goiania</xMun>
        <UF>GO</UF>
        <CEP>74000000</CEP>
      </enderEmit>
    </emit>
    <det nItem="1">
      <prod>
        <cProd>SKU-1</cProd>
        <xProd>Produto fiscal de teste</xProd>
        <NCM>01012100</NCM>
        <CFOP>5102</CFOP>
        <uCom>UN</uCom>
        <qCom>2.0000</qCom>
        <vUnCom>50.00</vUnCom>
        <vProd>100.00</vProd>
      </prod>
      <imposto>
        <ICMS>
          <ICMS00>
            <CST>00</CST>
            <pICMS>18.00</pICMS>
            <vICMS>18.00</vICMS>
          </ICMS00>
        </ICMS>
      </imposto>
    </det>
    <total>
      <ICMSTot>
        <vProd>100.00</vProd>
        <vNF>100.00</vNF>
      </ICMSTot>
    </total>
  </infNFe>
</NFe>
"""

# XML de NFC-e modelo 65 sem namespace
XML_NFCE_65_SIMPLES = """
<NFe>
  <infNFe Id="NFe35240112345678000195650010000004561000000048">
    <ide>
      <mod>65</mod>
      <serie>1</serie>
      <nNF>456</nNF>
      <dhEmi>2024-06-15T14:20:00-03:00</dhEmi>
      <natOp>Venda a consumidor</natOp>
      <tpNF>1</tpNF>
    </ide>
    <emit>
      <CNPJ>12345678000195</CNPJ>
      <xNome>LOJA TESTE LTDA</xNome>
    </emit>
    <dest>
      <CPF>12345678901</CPF>
      <xNome>CONSUMIDOR</xNome>
    </dest>
    <det nItem="1">
      <prod>
        <cProd>ITEM-01</cProd>
        <xProd>Item de consumo</xProd>
        <NCM>22021000</NCM>
        <CFOP>5102</CFOP>
        <uCom>UN</uCom>
        <qCom>1.0000</qCom>
        <vUnCom>25.00</vUnCom>
        <vProd>25.00</vProd>
      </prod>
      <imposto>
        <ICMS>
          <ICMS00>
            <CST>00</CST>
            <pICMS>12.00</pICMS>
            <vICMS>3.00</vICMS>
          </ICMS00>
        </ICMS>
      </imposto>
    </det>
    <total>
      <ICMSTot>
        <vProd>25.00</vProd>
        <vNF>25.00</vNF>
      </ICMSTot>
    </total>
  </infNFe>
</NFe>
"""

# XML com involucro nfeProc
XML_NFE_COM_PROC = """
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe35240112345678000195550010000001231000000012">
      <ide>
        <mod>55</mod>
        <serie>1</serie>
        <nNF>123</nNF>
        <dhEmi>2024-01-31T10:30:00-03:00</dhEmi>
        <natOp>Venda de mercadoria</natOp>
        <tpNF>1</tpNF>
      </ide>
      <emit>
        <CNPJ>12345678000195</CNPJ>
        <xNome>EMPRESA TESTE LTDA</xNome>
      </emit>
      <total>
        <ICMSTot>
          <vProd>100.00</vProd>
          <vNF>100.00</vNF>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
  <protNFe>
    <infProt>
      <nProt>135240000000001</nProt>
    </infProt>
  </protNFe>
</nfeProc>
"""

# XML invalido sem infNFe
XML_SEM_INF_NFE = "<raiz><dados>invalido</dados></raiz>"

# XML com Id invalido (prefixo correto mas menos de 44 digitos)
XML_COM_ID_INVALIDO = """
<NFe>
  <infNFe Id="NFe1234">
    <ide><mod>55</mod></ide>
  </infNFe>
</NFe>
"""

# XML com Id sem digitos (apenas texto)
XML_COM_ID_NAO_NUMERICO = """
<NFe>
  <infNFe Id="INVALIDO_NAO_NUMERICO_AAAAAAAAAAA_BBBBBBBBBBB_CCCCCCCCCC">
    <ide><mod>55</mod></ide>
  </infNFe>
</NFe>
"""


class TestParseNFeDocumentoSucesso:
    """Testes de parse bem-sucedido de NF-e e NFC-e."""

    def test_parse_nfe_modelo_55_extrai_chave_e_campos(self) -> None:
        """Parse de NF-e modelo 55 deve extrair chave, numero, serie e modelo."""
        resultado = parse_nfe_documento(XML_NFE_55_SIMPLES)

        assert resultado.chave_acesso == "35240112345678000195550010000001231000000012"
        assert resultado.número == "123"
        assert resultado.serie == "1"
        assert resultado.modelo == "55"

    def test_parse_nfe_modelo_55_extrai_emitente(self) -> None:
        """Parse de NF-e deve extrair dados do emitente corretamente."""
        resultado = parse_nfe_documento(XML_NFE_55_SIMPLES)

        assert resultado.emitente is not None
        assert resultado.emitente.cnpj == "12345678000195"
        assert resultado.emitente.nome == "EMPRESA TESTE LTDA"

    def test_parse_nfe_modelo_55_extrai_itens(self) -> None:
        """Parse de NF-e deve extrair pelo menos 1 item."""
        resultado = parse_nfe_documento(XML_NFE_55_SIMPLES)

        assert len(resultado.itens) == 1
        item = resultado.itens[0]
        assert item.codigo_produto == "SKU-1"
        assert item.valor_total == 100.0

    def test_parse_nfe_modelo_55_extrai_totais(self) -> None:
        """Parse de NF-e deve extrair totais da nota."""
        resultado = parse_nfe_documento(XML_NFE_55_SIMPLES)

        assert resultado.totais is not None
        assert resultado.totais.valor_nota == 100.0

    def test_parse_nfce_modelo_65_extrai_chave_e_modelo(self) -> None:
        """Parse de NFC-e modelo 65 deve extrair chave e identificar modelo 65."""
        resultado = parse_nfe_documento(XML_NFCE_65_SIMPLES)

        assert resultado.chave_acesso == "35240112345678000195650010000004561000000048"
        assert resultado.modelo == "65"
        assert resultado.número == "456"

    def test_parse_nfe_com_nfeproc_extrai_protocolo(self) -> None:
        """Parse de NF-e com involucro nfeProc deve extrair protocolo de autorizacao."""
        resultado = parse_nfe_documento(XML_NFE_COM_PROC)

        assert resultado.chave_acesso == "35240112345678000195550010000001231000000012"
        assert resultado.protocolo_autorizacao == "135240000000001"

    def test_parse_aceita_bytes(self) -> None:
        """Parse deve aceitar XML como bytes alem de string."""
        resultado = parse_nfe_documento(XML_NFE_55_SIMPLES.encode("utf-8"))

        assert resultado.chave_acesso == "35240112345678000195550010000001231000000012"

    def test_resultado_e_nfe_response(self) -> None:
        """O retorno deve ser uma instancia de NFeResponse com sucesso=True."""
        from mcp_fiscal_brasil.nfe.schemas import NFeResponse

        resultado = parse_nfe_documento(XML_NFE_55_SIMPLES)

        assert isinstance(resultado, NFeResponse)
        assert resultado.sucesso is True


class TestParseNFeDocumentoErros:
    """Testes de tratamento de erros no parse."""

    def test_xml_sem_inf_nfe_lanca_documento_parse_error(self) -> None:
        """XML sem elemento infNFe deve levantar DocumentoParseError."""
        with pytest.raises(DocumentoParseError) as exc_info:
            parse_nfe_documento(XML_SEM_INF_NFE)

        assert "infNFe" in str(exc_info.value)

    def test_xml_com_id_invalido_lanca_documento_parse_error(self) -> None:
        """XML com Id de infNFe invalido deve levantar DocumentoParseError."""
        with pytest.raises(DocumentoParseError) as exc_info:
            parse_nfe_documento(XML_COM_ID_INVALIDO)

        assert "44" in str(exc_info.value)

    def test_xml_com_id_nao_numerico_lanca_documento_parse_error(self) -> None:
        """XML com Id nao numerico deve levantar DocumentoParseError."""
        with pytest.raises(DocumentoParseError):
            parse_nfe_documento(XML_COM_ID_NAO_NUMERICO)

    def test_xml_malformado_lanca_excecao(self) -> None:
        """XML malformado deve levantar excecao de parse XML."""
        from mcp_fiscal_brasil.shared.exceptions import XMLParseError

        with pytest.raises((XMLParseError, FiscalValidationError)):
            parse_nfe_documento("<nao-fechado>")

    def test_documento_parse_error_e_fiscal_validation_error(self) -> None:
        """DocumentoParseError deve herdar de FiscalValidationError."""
        with pytest.raises(FiscalValidationError):
            parse_nfe_documento(XML_SEM_INF_NFE)
