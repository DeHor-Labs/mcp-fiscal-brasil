"""Testes para geracao de DANFE em PDF (nfe/danfe.py)."""

import base64

import pytest

from mcp_fiscal_brasil._core.errors import FiscalValidationError
from mcp_fiscal_brasil.nfe.danfe import DanfeGenerationError, DanfeResult, gerar_danfe

# XML completo de NF-e modelo 55 com namespace portalfiscal e protocolo.
# Necessario namespace pois a lib brazilfiscalreport usa ET.fromstring com URL namespaced.
XML_NFE_55_COMPLETO = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe35240112345678000195550010000001231000000012" versao="4.00">
      <ide>
        <cUF>35</cUF>
        <cNF>10000001</cNF>
        <natOp>Venda de mercadoria</natOp>
        <mod>55</mod>
        <serie>1</serie>
        <nNF>123</nNF>
        <dhEmi>2024-01-31T10:30:00-03:00</dhEmi>
        <tpNF>1</tpNF>
        <idDest>1</idDest>
        <cMunFG>3550308</cMunFG>
        <tpImp>1</tpImp>
        <tpEmis>1</tpEmis>
        <cDV>2</cDV>
        <tpAmb>2</tpAmb>
        <finNFe>1</finNFe>
        <indFinal>0</indFinal>
        <indPres>0</indPres>
        <procEmi>0</procEmi>
        <verProc>1.0</verProc>
      </ide>
      <emit>
        <CNPJ>12345678000195</CNPJ>
        <xNome>EMPRESA TESTE LTDA</xNome>
        <xFant>TESTE</xFant>
        <enderEmit>
          <xLgr>Rua Fiscal</xLgr>
          <nro>100</nro>
          <xBairro>Centro</xBairro>
          <cMun>3550308</cMun>
          <xMun>Sao Paulo</xMun>
          <UF>SP</UF>
          <CEP>01001000</CEP>
          <cPais>1058</cPais>
          <xPais>Brasil</xPais>
        </enderEmit>
        <IE>111111111111</IE>
        <CRT>3</CRT>
      </emit>
      <det nItem="1">
        <prod>
          <cProd>SKU-1</cProd>
          <cEAN>SEM GTIN</cEAN>
          <xProd>Produto fiscal de teste</xProd>
          <NCM>01012100</NCM>
          <CFOP>5102</CFOP>
          <uCom>UN</uCom>
          <qCom>2.0000</qCom>
          <vUnCom>50.00</vUnCom>
          <vProd>100.00</vProd>
          <cEANTrib>SEM GTIN</cEANTrib>
          <uTrib>UN</uTrib>
          <qTrib>2.0000</qTrib>
          <vUnTrib>50.00</vUnTrib>
          <indTot>1</indTot>
        </prod>
        <imposto>
          <ICMS>
            <ICMS00>
              <orig>0</orig>
              <CST>00</CST>
              <modBC>3</modBC>
              <vBC>100.00</vBC>
              <pICMS>18.00</pICMS>
              <vICMS>18.00</vICMS>
            </ICMS00>
          </ICMS>
          <PIS>
            <PISAliq>
              <CST>01</CST>
              <vBC>100.00</vBC>
              <pPIS>0.65</pPIS>
              <vPIS>0.65</vPIS>
            </PISAliq>
          </PIS>
          <COFINS>
            <COFINSAliq>
              <CST>01</CST>
              <vBC>100.00</vBC>
              <pCOFINS>3.00</pCOFINS>
              <vCOFINS>3.00</vCOFINS>
            </COFINSAliq>
          </COFINS>
        </imposto>
      </det>
      <total>
        <ICMSTot>
          <vBC>100.00</vBC>
          <vICMS>18.00</vICMS>
          <vICMSDeson>0.00</vICMSDeson>
          <vFCP>0.00</vFCP>
          <vBCST>0.00</vBCST>
          <vST>0.00</vST>
          <vFCPST>0.00</vFCPST>
          <vFCPSTRet>0.00</vFCPSTRet>
          <vProd>100.00</vProd>
          <vFrete>0.00</vFrete>
          <vSeg>0.00</vSeg>
          <vDesc>0.00</vDesc>
          <vII>0.00</vII>
          <vIPI>0.00</vIPI>
          <vIPIDevol>0.00</vIPIDevol>
          <vPIS>0.65</vPIS>
          <vCOFINS>3.00</vCOFINS>
          <vOutro>0.00</vOutro>
          <vNF>100.00</vNF>
        </ICMSTot>
      </total>
      <transp>
        <modFrete>9</modFrete>
      </transp>
    </infNFe>
  </NFe>
  <protNFe versao="4.00">
    <infProt>
      <tpAmb>2</tpAmb>
      <verAplic>SP_NFE_PL_008i2</verAplic>
      <chNFe>35240112345678000195550010000001231000000012</chNFe>
      <dhRecbto>2024-01-31T10:31:00-03:00</dhRecbto>
      <nProt>135240000000001</nProt>
      <digVal>AAAAAAAAAAAAAAAAAAAAAAAAAAAA</digVal>
      <cStat>100</cStat>
      <xMotivo>Autorizado o uso da NF-e</xMotivo>
    </infProt>
  </protNFe>
</nfeProc>
"""

# XML de NFC-e modelo 65 com namespace portalfiscal (sem involucro protNFe,
# pois NFC-e pode ser emitida offline)
XML_NFCE_65_COMPLETO = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe35240112345678000195650010000004561000000048" versao="4.00">
      <ide>
        <cUF>35</cUF>
        <cNF>10000045</cNF>
        <natOp>Venda a consumidor</natOp>
        <mod>65</mod>
        <serie>1</serie>
        <nNF>456</nNF>
        <dhEmi>2024-06-15T14:20:00-03:00</dhEmi>
        <tpNF>1</tpNF>
        <idDest>1</idDest>
        <cMunFG>3550308</cMunFG>
        <tpImp>4</tpImp>
        <tpEmis>1</tpEmis>
        <cDV>8</cDV>
        <tpAmb>2</tpAmb>
        <finNFe>1</finNFe>
        <indFinal>1</indFinal>
        <indPres>1</indPres>
        <procEmi>0</procEmi>
        <verProc>1.0</verProc>
      </ide>
      <emit>
        <CNPJ>12345678000195</CNPJ>
        <xNome>LOJA TESTE LTDA</xNome>
        <enderEmit>
          <xLgr>Rua Comercio</xLgr>
          <nro>200</nro>
          <xBairro>Centro</xBairro>
          <cMun>3550308</cMun>
          <xMun>Sao Paulo</xMun>
          <UF>SP</UF>
          <CEP>01001000</CEP>
          <cPais>1058</cPais>
          <xPais>Brasil</xPais>
        </enderEmit>
        <IE>111111111111</IE>
        <CRT>3</CRT>
      </emit>
      <det nItem="1">
        <prod>
          <cProd>ITEM-01</cProd>
          <cEAN>SEM GTIN</cEAN>
          <xProd>Item de consumo</xProd>
          <NCM>22021000</NCM>
          <CFOP>5102</CFOP>
          <uCom>UN</uCom>
          <qCom>1.0000</qCom>
          <vUnCom>25.00</vUnCom>
          <vProd>25.00</vProd>
          <cEANTrib>SEM GTIN</cEANTrib>
          <uTrib>UN</uTrib>
          <qTrib>1.0000</qTrib>
          <vUnTrib>25.00</vUnTrib>
          <indTot>1</indTot>
        </prod>
        <imposto>
          <ICMS>
            <ICMS00>
              <orig>0</orig>
              <CST>00</CST>
              <modBC>3</modBC>
              <vBC>25.00</vBC>
              <pICMS>12.00</pICMS>
              <vICMS>3.00</vICMS>
            </ICMS00>
          </ICMS>
          <PIS>
            <PISAliq>
              <CST>01</CST>
              <vBC>25.00</vBC>
              <pPIS>0.65</pPIS>
              <vPIS>0.16</vPIS>
            </PISAliq>
          </PIS>
          <COFINS>
            <COFINSAliq>
              <CST>01</CST>
              <vBC>25.00</vBC>
              <pCOFINS>3.00</pCOFINS>
              <vCOFINS>0.75</vCOFINS>
            </COFINSAliq>
          </COFINS>
        </imposto>
      </det>
      <total>
        <ICMSTot>
          <vBC>25.00</vBC>
          <vICMS>3.00</vICMS>
          <vICMSDeson>0.00</vICMSDeson>
          <vFCP>0.00</vFCP>
          <vBCST>0.00</vBCST>
          <vST>0.00</vST>
          <vFCPST>0.00</vFCPST>
          <vFCPSTRet>0.00</vFCPSTRet>
          <vProd>25.00</vProd>
          <vFrete>0.00</vFrete>
          <vSeg>0.00</vSeg>
          <vDesc>0.00</vDesc>
          <vII>0.00</vII>
          <vIPI>0.00</vIPI>
          <vIPIDevol>0.00</vIPIDevol>
          <vPIS>0.16</vPIS>
          <vCOFINS>0.75</vCOFINS>
          <vOutro>0.00</vOutro>
          <vNF>25.00</vNF>
        </ICMSTot>
      </total>
      <transp>
        <modFrete>9</modFrete>
      </transp>
    </infNFe>
  </NFe>
  <protNFe versao="4.00">
    <infProt>
      <tpAmb>2</tpAmb>
      <verAplic>SP_NFE_PL_008i2</verAplic>
      <chNFe>35240112345678000195650010000004561000000048</chNFe>
      <dhRecbto>2024-06-15T14:21:00-03:00</dhRecbto>
      <nProt>265240000000001</nProt>
      <cStat>100</cStat>
      <xMotivo>Autorizado o uso da NF-e</xMotivo>
    </infProt>
  </protNFe>
</nfeProc>
"""

# XML invalido sem infNFe
XML_SEM_INF_NFE = "<raiz><dados>invalido</dados></raiz>"


class TestGerarDanfeNFe:
    """Testes de geracao de DANFE para NF-e modelo 55."""

    def test_gera_pdf_para_nfe_55(self) -> None:
        """Deve gerar PDF valido (header %PDF) para NF-e modelo 55."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        pdf_bytes = base64.b64decode(resultado.pdf_base64)
        assert pdf_bytes[:4] == b"%PDF", "PDF deve comecar com '%PDF'"

    def test_resultado_e_danfe_result(self) -> None:
        """O retorno deve ser instancia de DanfeResult."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        assert isinstance(resultado, DanfeResult)

    def test_modelo_retornado_e_55(self) -> None:
        """DanfeResult deve informar modelo 55 para NF-e."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        assert resultado.modelo == 55

    def test_pdf_nao_e_vazio(self) -> None:
        """PDF gerado nao deve ser vazio."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        pdf_bytes = base64.b64decode(resultado.pdf_base64)
        assert len(pdf_bytes) > 100, "PDF deve ter conteudo substancial"

    def test_nome_arquivo_contem_chave(self) -> None:
        """nome_arquivo deve conter a chave de acesso."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        assert "35240112345678000195550010000001231000000012" in resultado.nome_arquivo

    def test_nome_arquivo_tem_extensao_pdf(self) -> None:
        """nome_arquivo deve terminar com .pdf."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        assert resultado.nome_arquivo.endswith(".pdf")

    def test_chave_acesso_retornada(self) -> None:
        """DanfeResult deve retornar a chave de acesso extraida do XML."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        assert resultado.chave_acesso == "35240112345678000195550010000001231000000012"

    def test_numero_e_serie_retornados(self) -> None:
        """DanfeResult deve retornar numero e serie da nota."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        assert resultado.numero == "123"
        assert resultado.serie == "1"

    def test_aceita_bytes(self) -> None:
        """Deve aceitar XML como bytes alem de string."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO.encode("utf-8"))

        pdf_bytes = base64.b64decode(resultado.pdf_base64)
        assert pdf_bytes[:4] == b"%PDF"

    def test_pdf_base64_e_decodificavel(self) -> None:
        """pdf_base64 deve ser base64 valido decodificavel sem erro."""
        resultado = gerar_danfe(XML_NFE_55_COMPLETO)

        # Nao deve levantar excecao
        decoded = base64.b64decode(resultado.pdf_base64)
        assert isinstance(decoded, bytes)


class TestGerarDanfeNFCe:
    """Testes de comportamento para NFC-e modelo 65.

    A brazilfiscalreport 1.0.0 nao possui classe dedicada a NFC-e.
    A decisao de implementacao e levantar DanfeGenerationError com mensagem
    clara ao inves de fallback silencioso, para evitar que o usuario
    receba um DANFE A4 gerado incorretamente para um cupom fiscal.
    """

    def test_nfce_65_lanca_danfe_generation_error(self) -> None:
        """NFC-e modelo 65 deve levantar DanfeGenerationError (nao suportado na v1.0.0)."""
        with pytest.raises(DanfeGenerationError) as exc_info:
            gerar_danfe(XML_NFCE_65_COMPLETO)

        msg = str(exc_info.value).lower()
        assert "65" in msg or "nfc" in msg or "suportado" in msg

    def test_nfce_65_mensagem_orienta_usuario(self) -> None:
        """Mensagem de erro para NFC-e deve orientar o usuario sobre a limitacao."""
        with pytest.raises(DanfeGenerationError) as exc_info:
            gerar_danfe(XML_NFCE_65_COMPLETO)

        # Mensagem deve mencionar o modelo ou a limitacao da versao
        assert "65" in str(exc_info.value) or "nao" in str(exc_info.value).lower()

    def test_nfce_65_e_fiscal_validation_error(self) -> None:
        """DanfeGenerationError para NFC-e deve herdar de FiscalValidationError."""
        with pytest.raises(FiscalValidationError):
            gerar_danfe(XML_NFCE_65_COMPLETO)


class TestGerarDanfeErros:
    """Testes de tratamento de erros na geracao de DANFE."""

    def test_xml_invalido_lanca_danfe_generation_error(self) -> None:
        """XML sem infNFe deve levantar DanfeGenerationError."""
        with pytest.raises(DanfeGenerationError) as exc_info:
            gerar_danfe(XML_SEM_INF_NFE)

        assert "infNFe" in str(exc_info.value)

    def test_danfe_generation_error_e_fiscal_validation_error(self) -> None:
        """DanfeGenerationError deve herdar de FiscalValidationError."""
        with pytest.raises(FiscalValidationError):
            gerar_danfe(XML_SEM_INF_NFE)

    def test_xml_malformado_lanca_excecao(self) -> None:
        """XML malformado deve levantar excecao de parse XML."""
        from mcp_fiscal_brasil.shared.exceptions import XMLParseError

        with pytest.raises((XMLParseError, FiscalValidationError)):
            gerar_danfe("<xml-nao-fechado>")

    def test_modelo_invalido_lanca_danfe_generation_error(self) -> None:
        """Modelo desconhecido (nao 55) deve levantar DanfeGenerationError."""
        # Nota: chave com modelo 99 no campo 21-22 da chave (posicao 20-21, base 0)
        # Para o teste, o importante e que o campo ide/mod=99 seja lido e rejeitado
        xml_modelo_invalido = """
        <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
          <infNFe Id="NFe35240112345678000195990010000001231000000012">
            <ide><mod>99</mod><serie>1</serie><nNF>1</nNF></ide>
            <emit><CNPJ>12345678000195</CNPJ><xNome>X</xNome></emit>
            <total><ICMSTot><vNF>0.00</vNF></ICMSTot></total>
            <transp><modFrete>9</modFrete></transp>
          </infNFe>
        </NFe>
        """
        with pytest.raises(DanfeGenerationError) as exc_info:
            gerar_danfe(xml_modelo_invalido)

        assert "99" in str(exc_info.value) or "suportado" in str(exc_info.value).lower()

    def test_xml_sem_namespace_lanca_danfe_generation_error(self) -> None:
        """XML de NF-e modelo 55 sem namespace portalfiscal deve levantar DanfeGenerationError."""
        xml_sem_namespace = """
        <NFe>
          <infNFe Id="NFe35240112345678000195550010000001231000000012">
            <ide><mod>55</mod><serie>1</serie><nNF>123</nNF></ide>
            <emit><CNPJ>12345678000195</CNPJ><xNome>EMPRESA</xNome></emit>
            <total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>
            <transp><modFrete>9</modFrete></transp>
          </infNFe>
        </NFe>
        """
        with pytest.raises(DanfeGenerationError) as exc_info:
            gerar_danfe(xml_sem_namespace)

        msg = str(exc_info.value)
        assert "namespace" in msg.lower() or "portalfiscal" in msg.lower()
