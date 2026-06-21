"""Tests for NFe XML parser edge cases."""

from mcp_fiscal_brasil.nfe.xml_parser import parse_nfe_xml


def test_parse_nfe_xml_without_namespace_extracts_basic_fields() -> None:
    xml = """
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
            <xMun>São Paulo</xMun>
            <UF>SP</UF>
            <CEP>01001000</CEP>
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

    response = parse_nfe_xml(xml, "35240112345678000195550010000001231000000012")

    assert response.número == "123"
    assert response.serie == "1"
    assert response.natureza_operacao == "Venda de mercadoria"
    assert response.emitente is not None
    assert response.emitente.cnpj == "12345678000195"
    assert len(response.itens) == 1
    assert response.itens[0].valor_total == 100.0
    assert response.totais is not None
    assert response.totais.valor_nota == 100.0


def test_parse_nfe_xml_extrai_chave_do_id_quando_chave_vazia() -> None:
    xml = """
    <NFe>
      <infNFe Id="NFe35240112345678000195550010000001231000000012">
        <ide>
          <mod>55</mod>
          <serie>1</serie>
          <nNF>123</nNF>
        </ide>
      </infNFe>
    </NFe>
    """

    response = parse_nfe_xml(xml, "")

    assert response.chave_acesso == "35240112345678000195550010000001231000000012"
