"""Testes para campos de Reforma Tributária (IBS/CBS/IS) no parser NF-e.

Baseado na NT 2025.002 - Adequação NF-e/NFC-e ao IBS, CBS e IS.
Grupo UB: det/imposto/IBSCBS com subgrupos IBSUF, IBSMun, CBS.
Totais Grupo W03: vBCIBSCBS, vIBSUF, vIBSMun, vIBS, vCBS, vIS.
"""

from mcp_fiscal_brasil.nfe.xml_parser import parse_nfe_xml

XML_NFE_COM_IBSCBS = """
<NFe>
  <infNFe Id="NFe35240112345678000195550010000001231000000012">
    <ide>
      <mod>55</mod>
      <serie>1</serie>
      <nNF>999</nNF>
      <dhEmi>2026-01-15T10:00:00-03:00</dhEmi>
      <natOp>Venda com Reforma Tributária</natOp>
      <tpNF>1</tpNF>
    </ide>
    <emit>
      <CNPJ>12345678000195</CNPJ>
      <xNome>EMPRESA REFORMA TRIBUTARIA LTDA</xNome>
    </emit>
    <det nItem="1">
      <prod>
        <cProd>PROD-RT-01</cProd>
        <xProd>Produto com IBS CBS IS</xProd>
        <NCM>84713012</NCM>
        <CFOP>5102</CFOP>
        <uCom>UN</uCom>
        <qCom>1.0000</qCom>
        <vUnCom>1000.00</vUnCom>
        <vProd>1000.00</vProd>
      </prod>
      <imposto>
        <ICMS>
          <ICMS00>
            <CST>00</CST>
            <pICMS>12.00</pICMS>
            <vICMS>120.00</vICMS>
          </ICMS00>
        </ICMS>
        <IBSCBS>
          <IBSUF>
            <vBC>1000.00</vBC>
            <pAliq>9.00</pAliq>
            <vIBSUF>90.00</vIBSUF>
          </IBSUF>
          <IBSMun>
            <vBC>1000.00</vBC>
            <pAliq>3.65</pAliq>
            <vIBSMun>36.50</vIBSMun>
          </IBSMun>
          <CBS>
            <vBC>1000.00</vBC>
            <pAliq>5.80</pAliq>
            <vCBS>58.00</vCBS>
          </CBS>
          <IS>
            <vBCIS>1000.00</vBCIS>
            <pIS>1.00</pIS>
            <vIS>10.00</vIS>
          </IS>
        </IBSCBS>
      </imposto>
    </det>
    <total>
      <ICMSTot>
        <vProd>1000.00</vProd>
        <vICMS>120.00</vICMS>
        <vNF>1000.00</vNF>
      </ICMSTot>
      <IBSCBSTot>
        <vBCIBSCBS>1000.00</vBCIBSCBS>
        <vIBSUF>90.00</vIBSUF>
        <vIBSMun>36.50</vIBSMun>
        <vIBS>126.50</vIBS>
        <vCBS>58.00</vCBS>
        <vIS>10.00</vIS>
      </IBSCBSTot>
    </total>
  </infNFe>
</NFe>
"""

XML_NFE_SEM_IBSCBS = """
<NFe>
  <infNFe Id="NFe35240112345678000195550010000001231000000099">
    <ide>
      <mod>55</mod>
      <serie>1</serie>
      <nNF>1</nNF>
      <dhEmi>2024-01-01T08:00:00-03:00</dhEmi>
      <natOp>Venda normal pre-reforma</natOp>
      <tpNF>1</tpNF>
    </ide>
    <emit>
      <CNPJ>12345678000195</CNPJ>
      <xNome>EMPRESA ANTIGA LTDA</xNome>
    </emit>
    <det nItem="1">
      <prod>
        <cProd>PROD-01</cProd>
        <xProd>Produto sem IBS CBS</xProd>
        <NCM>84713012</NCM>
        <CFOP>5102</CFOP>
        <uCom>UN</uCom>
        <qCom>5.0000</qCom>
        <vUnCom>200.00</vUnCom>
        <vProd>1000.00</vProd>
      </prod>
      <imposto>
        <ICMS>
          <ICMS00>
            <CST>00</CST>
            <pICMS>12.00</pICMS>
            <vICMS>120.00</vICMS>
          </ICMS00>
        </ICMS>
      </imposto>
    </det>
    <total>
      <ICMSTot>
        <vProd>1000.00</vProd>
        <vICMS>120.00</vICMS>
        <vNF>1000.00</vNF>
      </ICMSTot>
    </total>
  </infNFe>
</NFe>
"""


class TestNFeIBSCBS:
    def test_parse_item_com_ibscbs_extrai_ibs_uf(self) -> None:
        resp = parse_nfe_xml(XML_NFE_COM_IBSCBS, "35240112345678000195550010000001231000000012")
        assert len(resp.itens) == 1
        item = resp.itens[0]
        assert item.aliquota_ibs_uf == 9.0
        assert item.valor_ibs_uf == 90.0

    def test_parse_item_com_ibscbs_extrai_ibs_mun(self) -> None:
        resp = parse_nfe_xml(XML_NFE_COM_IBSCBS, "35240112345678000195550010000001231000000012")
        item = resp.itens[0]
        assert item.aliquota_ibs_mun == 3.65
        assert item.valor_ibs_mun == 36.5

    def test_parse_item_com_ibscbs_extrai_cbs(self) -> None:
        resp = parse_nfe_xml(XML_NFE_COM_IBSCBS, "35240112345678000195550010000001231000000012")
        item = resp.itens[0]
        assert item.aliquota_cbs == 5.80
        assert item.valor_cbs == 58.0

    def test_parse_item_com_ibscbs_extrai_is(self) -> None:
        resp = parse_nfe_xml(XML_NFE_COM_IBSCBS, "35240112345678000195550010000001231000000012")
        item = resp.itens[0]
        assert item.aliquota_is == 1.0
        assert item.valor_is == 10.0

    def test_parse_totais_reforma_extraidos(self) -> None:
        resp = parse_nfe_xml(XML_NFE_COM_IBSCBS, "35240112345678000195550010000001231000000012")
        assert resp.totais_reforma is not None
        assert resp.totais_reforma.base_calculo_ibscbs == 1000.0
        assert resp.totais_reforma.valor_ibs_uf == 90.0
        assert resp.totais_reforma.valor_ibs_mun == 36.5
        assert resp.totais_reforma.valor_ibs == 126.5
        assert resp.totais_reforma.valor_cbs == 58.0
        assert resp.totais_reforma.valor_is == 10.0

    def test_parse_nfe_pre_reforma_sem_ibscbs_compativel(self) -> None:
        """NF-e sem grupos IBS/CBS/IS não deve quebrar - campos ficam None."""
        resp = parse_nfe_xml(XML_NFE_SEM_IBSCBS, "35240112345678000195550010000001231000000099")
        assert resp.totais_reforma is None
        item = resp.itens[0]
        assert item.aliquota_ibs_uf is None
        assert item.valor_ibs_uf is None
        assert item.aliquota_cbs is None
        assert item.valor_cbs is None
        assert item.aliquota_is is None
        assert item.valor_is is None

    def test_parse_nfe_pre_reforma_icms_continua_funcionando(self) -> None:
        """Campos ICMS legados não são afetados pela adição dos campos RT."""
        resp = parse_nfe_xml(XML_NFE_SEM_IBSCBS, "35240112345678000195550010000001231000000099")
        assert resp.totais is not None
        assert resp.totais.valor_icms == 120.0
        assert resp.totais.valor_nota == 1000.0
        assert resp.itens[0].aliquota_icms == 12.0
        assert resp.itens[0].valor_icms == 120.0
