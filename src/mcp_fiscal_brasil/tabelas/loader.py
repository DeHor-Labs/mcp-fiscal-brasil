"""
Loader de tabelas fiscais estáticas para o módulo tabelas.

Estratégia de armazenamento:
  - CFOP, CST/CSOSN, alíquotas ICMS: dicionários em memória (pequenos e estáveis).
  - NCM e CEST: SQLite bundled em data/tabelas_fiscais.db (tabelas grandes).

AVISO NCM/CEST: O banco SQLite distribuído contém um subconjunto representativo dos
capítulos NCM mais comuns (~250 registros de exemplo) e segmentos CEST (~100 registros).
A tabela NCM completa da TIPI possui ~10.515 registros. Para popular o banco completo,
execute: python scripts/build_tabelas_db.py --tipi tipi.csv --cest cest.csv
"""

from __future__ import annotations

import importlib.resources
import sqlite3
from pathlib import Path
from typing import Any

from mcp_fiscal_brasil._core import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# CFOP - Código Fiscal de Operações e Prestações (Convênio SINIEF s/n, 1970)
# Tabela completa com os grupos principais. Formato: código -> (descrição, tipo, aplicação)
# tipo: "entrada" | "saida"
# aplicacao: "estadual" | "interestadual" | "exterior"
# ---------------------------------------------------------------------------

CFOP_TABLE: dict[str, tuple[str, str, str]] = {
    # Grupo 1 - Entradas estaduais (dentro do estado)
    "1100": (
        "Compras para industrialização, produção rural, comercialização ou prestação de serviços",
        "entrada",
        "estadual",
    ),
    "1101": ("Compra para industrialização ou produção rural", "entrada", "estadual"),
    "1102": ("Compra para comercialização", "entrada", "estadual"),
    "1111": (
        "Compra para industrialização de mercadoria recebida anteriormente em consignação mercantil",
        "entrada",
        "estadual",
    ),
    "1113": (
        "Compra para comercialização de mercadoria recebida anteriormente em consignação mercantil",
        "entrada",
        "estadual",
    ),
    "1116": (
        "Compra para industrialização originada de encomenda para recebimento futuro",
        "entrada",
        "estadual",
    ),
    "1117": (
        "Compra para comercialização originada de encomenda para recebimento futuro",
        "entrada",
        "estadual",
    ),
    "1118": (
        "Compra de mercadoria para comercialização pelo adquirente originário",
        "entrada",
        "estadual",
    ),
    "1120": (
        "Compra para industrialização, em venda à ordem, já recebida do vendedor remetente",
        "entrada",
        "estadual",
    ),
    "1121": (
        "Compra para comercialização, em venda à ordem, já recebida do vendedor remetente",
        "entrada",
        "estadual",
    ),
    "1122": (
        "Compra para industrialização em que a mercadoria foi remetida pelo fornecedor ao industrializador",
        "entrada",
        "estadual",
    ),
    "1124": ("Industrialização efetuada por outra empresa", "entrada", "estadual"),
    "1125": (
        "Industrialização efetuada por outra empresa quando a mercadoria remetida para esse fim era originária de terceiro",
        "entrada",
        "estadual",
    ),
    "1126": (
        "Compra para utilização na prestação de serviço sujeita ao ISSQN",
        "entrada",
        "estadual",
    ),
    "1128": (
        "Compra para utilização na prestação de serviço sujeita ao ICMS",
        "entrada",
        "estadual",
    ),
    "1150": (
        "Transferências para industrialização, produção rural, comercialização ou prestação de serviços",
        "entrada",
        "estadual",
    ),
    "1151": ("Transferência para industrialização ou produção rural", "entrada", "estadual"),
    "1152": ("Transferência para comercialização", "entrada", "estadual"),
    "1153": ("Transferência de energia elétrica para distribuição", "entrada", "estadual"),
    "1154": ("Transferência para utilização na prestação de serviço", "entrada", "estadual"),
    "1200": (
        "Devoluções de vendas de produção própria, de terceiros ou anulações de valores",
        "entrada",
        "estadual",
    ),
    "1201": ("Devolução de venda de produção do estabelecimento", "entrada", "estadual"),
    "1202": (
        "Devolução de venda de mercadoria adquirida ou recebida de terceiros",
        "entrada",
        "estadual",
    ),
    "1203": (
        "Devolução de venda de produção do estabelecimento destinada à Zona Franca de Manaus ou Áreas de Livre Comércio",
        "entrada",
        "estadual",
    ),
    "1204": (
        "Devolução de venda de mercadoria adquirida ou recebida de terceiros destinada à Zona Franca de Manaus ou Áreas de Livre Comércio",
        "entrada",
        "estadual",
    ),
    "1205": (
        "Anulação de valor relativo à prestação de serviço de comunicação",
        "entrada",
        "estadual",
    ),
    "1206": (
        "Anulação de valor relativo à prestação de serviço de transporte",
        "entrada",
        "estadual",
    ),
    "1207": ("Anulação de valor relativo à venda de energia elétrica", "entrada", "estadual"),
    "1208": (
        "Devolução de produção do estabelecimento remetida em transferência",
        "entrada",
        "estadual",
    ),
    "1209": (
        "Devolução de mercadoria adquirida ou recebida de terceiros remetida em transferência",
        "entrada",
        "estadual",
    ),
    "1250": ("Compras de energia elétrica", "entrada", "estadual"),
    "1251": (
        "Compra de energia elétrica para distribuição ou comercialização",
        "entrada",
        "estadual",
    ),
    "1252": ("Compra de energia elétrica por estabelecimento industrial", "entrada", "estadual"),
    "1253": ("Compra de energia elétrica por estabelecimento comercial", "entrada", "estadual"),
    "1254": (
        "Compra de energia elétrica por estabelecimento prestador de serviço de transporte",
        "entrada",
        "estadual",
    ),
    "1255": (
        "Compra de energia elétrica por estabelecimento prestador de serviço de comunicação",
        "entrada",
        "estadual",
    ),
    "1256": (
        "Compra de energia elétrica por estabelecimento de produtor rural",
        "entrada",
        "estadual",
    ),
    "1257": (
        "Compra de energia elétrica para consumo por demanda contratada",
        "entrada",
        "estadual",
    ),
    "1300": ("Aquisições de serviços de comunicação", "entrada", "estadual"),
    "1301": (
        "Aquisição de serviço de comunicação para execução de serviço da mesma natureza",
        "entrada",
        "estadual",
    ),
    "1302": (
        "Aquisição de serviço de comunicação por estabelecimento industrial",
        "entrada",
        "estadual",
    ),
    "1303": (
        "Aquisição de serviço de comunicação por estabelecimento comercial",
        "entrada",
        "estadual",
    ),
    "1400": ("Aquisições de serviços de transporte", "entrada", "estadual"),
    "1401": (
        "Aquisição de serviço de transporte para execução de serviço da mesma natureza",
        "entrada",
        "estadual",
    ),
    "1403": (
        "Aquisição de serviço de transporte por estabelecimento industrial",
        "entrada",
        "estadual",
    ),
    "1404": (
        "Aquisição de serviço de transporte por estabelecimento comercial",
        "entrada",
        "estadual",
    ),
    "1407": (
        "Aquisição de serviço de transporte por estabelecimento prestador de serviço de comunicação",
        "entrada",
        "estadual",
    ),
    "1408": (
        "Aquisição de serviço de transporte por estabelecimento de produtor rural",
        "entrada",
        "estadual",
    ),
    "1409": (
        "Aquisição de serviço de transporte por estabelecimento das demais atividades",
        "entrada",
        "estadual",
    ),
    "1500": (
        "Entradas de mercadorias remetidas com fim específico de exportação e eventuais devoluções",
        "entrada",
        "estadual",
    ),
    "1501": (
        "Entrada de mercadoria recebida com fim específico de exportação",
        "entrada",
        "estadual",
    ),
    "1503": (
        "Entrada decorrente de devolução de produto remetido com o fim específico de exportação",
        "entrada",
        "estadual",
    ),
    "1550": (
        "Operações com bens de ativo imobilizado e materiais para uso ou consumo",
        "entrada",
        "estadual",
    ),
    "1551": ("Compra de bem para o ativo imobilizado", "entrada", "estadual"),
    "1552": ("Transferência de bem do ativo imobilizado", "entrada", "estadual"),
    "1553": ("Devolução de venda de bem do ativo imobilizado", "entrada", "estadual"),
    "1554": (
        "Retorno de bem do ativo imobilizado remetido para uso fora do estabelecimento",
        "entrada",
        "estadual",
    ),
    "1555": (
        "Entrada de bem do ativo imobilizado de terceiro remetido para uso no estabelecimento",
        "entrada",
        "estadual",
    ),
    "1556": ("Compra de material para uso ou consumo", "entrada", "estadual"),
    "1557": ("Transferência de material para uso ou consumo", "entrada", "estadual"),
    "1600": ("Créditos e ressarcimentos de ICMS", "entrada", "estadual"),
    "1601": ("Recebimento, por transferência, de crédito de ICMS", "entrada", "estadual"),
    "1602": (
        "Recebimento, por transferência, de saldo credor de ICMS de outro estabelecimento da mesma empresa",
        "entrada",
        "estadual",
    ),
    "1603": ("Ressarcimento de ICMS retido por substituição tributária", "entrada", "estadual"),
    "1604": (
        "Lançamento do crédito relativo à compra de bem para o ativo imobilizado",
        "entrada",
        "estadual",
    ),
    "1650": (
        "Entradas de combustíveis, lubrificantes, aditivos e agentes de limpeza",
        "entrada",
        "estadual",
    ),
    "1651": ("Compra de combustível ou lubrificante para industrialização", "entrada", "estadual"),
    "1652": ("Compra de combustível ou lubrificante para comercialização", "entrada", "estadual"),
    "1653": (
        "Compra de combustível ou lubrificante por consumidor ou usuário final",
        "entrada",
        "estadual",
    ),
    "1658": (
        "Transferência de combustível ou lubrificante para industrialização",
        "entrada",
        "estadual",
    ),
    "1659": (
        "Transferência de combustível ou lubrificante para comercialização",
        "entrada",
        "estadual",
    ),
    "1660": (
        "Devolução de venda de combustível ou lubrificante destinado à industrialização",
        "entrada",
        "estadual",
    ),
    "1661": (
        "Devolução de venda de combustível ou lubrificante destinado à comercialização",
        "entrada",
        "estadual",
    ),
    "1662": (
        "Devolução de venda de combustível ou lubrificante destinado a consumidor ou usuário final",
        "entrada",
        "estadual",
    ),
    "1700": ("Entradas de mercadorias em operações com veículos novos", "entrada", "estadual"),
    "1750": (
        "Entradas de sucata e de produtos primários com diferimento de pagamento do imposto",
        "entrada",
        "estadual",
    ),
    "1800": (
        "Entradas de mercadorias sujeitas ao regime de substituição tributária",
        "entrada",
        "estadual",
    ),
    "1900": (
        "Outras entradas de mercadorias ou aquisições de serviços não especificadas",
        "entrada",
        "estadual",
    ),
    "1901": (
        "Entrada para industrialização por conta e ordem do adquirente da mercadoria",
        "entrada",
        "estadual",
    ),
    "1902": (
        "Retorno de mercadoria remetida para industrialização por conta e ordem do adquirente",
        "entrada",
        "estadual",
    ),
    "1903": (
        "Entrada de mercadoria remetida para industrialização e não aplicada no referido processo",
        "entrada",
        "estadual",
    ),
    "1904": ("Retorno de remessa para venda fora do estabelecimento", "entrada", "estadual"),
    "1905": (
        "Entrada de mercadoria recebida para depósito em depósito fechado ou armazém alfandegado",
        "entrada",
        "estadual",
    ),
    "1906": (
        "Retorno de mercadoria remetida para depósito fechado ou armazém alfandegado",
        "entrada",
        "estadual",
    ),
    "1907": (
        "Retorno simbólico de mercadoria remetida para depósito fechado ou armazém alfandegado",
        "entrada",
        "estadual",
    ),
    "1908": ("Entrada de bem por conta de contrato de comodato", "entrada", "estadual"),
    "1909": ("Retorno de bem remetido por conta de contrato de comodato", "entrada", "estadual"),
    "1910": ("Entrada de bonificação, doação ou brinde", "entrada", "estadual"),
    "1911": ("Entrada de amostra grátis", "entrada", "estadual"),
    "1912": ("Entrada de mercadoria ou bem recebido para demonstração", "entrada", "estadual"),
    "1913": ("Retorno de mercadoria ou bem remetido para demonstração", "entrada", "estadual"),
    "1914": (
        "Retorno de mercadoria ou bem remetido para exposição ou feira",
        "entrada",
        "estadual",
    ),
    "1915": (
        "Entrada de mercadoria ou bem recebido para conserto ou reparo",
        "entrada",
        "estadual",
    ),
    "1916": (
        "Retorno de mercadoria ou bem remetido para conserto ou reparo",
        "entrada",
        "estadual",
    ),
    "1917": (
        "Entrada de mercadoria recebida em consignação mercantil ou industrial",
        "entrada",
        "estadual",
    ),
    "1918": (
        "Devolução de mercadoria remetida em consignação mercantil ou industrial",
        "entrada",
        "estadual",
    ),
    "1919": (
        "Devolução simbólica de mercadoria vendida ou utilizada em processo industrial",
        "entrada",
        "estadual",
    ),
    "1920": ("Entrada de vasilhame ou sacaria", "entrada", "estadual"),
    "1921": ("Retorno de vasilhame ou sacaria", "entrada", "estadual"),
    "1922": (
        "Lançamento efetuado a título de simples faturamento decorrente de compra para recebimento futuro",
        "entrada",
        "estadual",
    ),
    "1923": (
        "Entrada de mercadoria em poder de terceiros decorrente de inventário",
        "entrada",
        "estadual",
    ),
    "1924": (
        "Entrada para reconhecimento de crédito de estoque fiscal de ICMS",
        "entrada",
        "estadual",
    ),
    "1925": (
        "Retorno de mercadoria remetida para armazenagem, exceto campo específico",
        "entrada",
        "estadual",
    ),
    "1926": (
        "Lançamento efetuado a título de reclassificação de mercadoria decorrente de formação de kit",
        "entrada",
        "estadual",
    ),
    "1949": (
        "Outra entrada de mercadoria ou prestação de serviço não especificada",
        "entrada",
        "estadual",
    ),
    # Grupo 2 - Entradas interestaduais
    "2100": (
        "Compras para industrialização, produção rural, comercialização ou prestação de serviços",
        "entrada",
        "interestadual",
    ),
    "2101": ("Compra para industrialização ou produção rural", "entrada", "interestadual"),
    "2102": ("Compra para comercialização", "entrada", "interestadual"),
    "2111": (
        "Compra para industrialização de mercadoria recebida anteriormente em consignação mercantil",
        "entrada",
        "interestadual",
    ),
    "2113": (
        "Compra para comercialização de mercadoria recebida anteriormente em consignação mercantil",
        "entrada",
        "interestadual",
    ),
    "2116": (
        "Compra para industrialização originada de encomenda para recebimento futuro",
        "entrada",
        "interestadual",
    ),
    "2117": (
        "Compra para comercialização originada de encomenda para recebimento futuro",
        "entrada",
        "interestadual",
    ),
    "2118": (
        "Compra de mercadoria para comercialização pelo adquirente originário",
        "entrada",
        "interestadual",
    ),
    "2120": (
        "Compra para industrialização, em venda à ordem, já recebida do vendedor remetente",
        "entrada",
        "interestadual",
    ),
    "2121": (
        "Compra para comercialização, em venda à ordem, já recebida do vendedor remetente",
        "entrada",
        "interestadual",
    ),
    "2122": (
        "Compra para industrialização em que a mercadoria foi remetida pelo fornecedor ao industrializador",
        "entrada",
        "interestadual",
    ),
    "2124": ("Industrialização efetuada por outra empresa", "entrada", "interestadual"),
    "2125": (
        "Industrialização efetuada por outra empresa quando a mercadoria remetida para esse fim era originária de terceiro",
        "entrada",
        "interestadual",
    ),
    "2126": (
        "Compra para utilização na prestação de serviço sujeita ao ISSQN",
        "entrada",
        "interestadual",
    ),
    "2128": (
        "Compra para utilização na prestação de serviço sujeita ao ICMS",
        "entrada",
        "interestadual",
    ),
    "2150": (
        "Transferências para industrialização, produção rural, comercialização ou prestação de serviços",
        "entrada",
        "interestadual",
    ),
    "2151": ("Transferência para industrialização ou produção rural", "entrada", "interestadual"),
    "2152": ("Transferência para comercialização", "entrada", "interestadual"),
    "2153": ("Transferência de energia elétrica para distribuição", "entrada", "interestadual"),
    "2154": ("Transferência para utilização na prestação de serviço", "entrada", "interestadual"),
    "2200": (
        "Devoluções de vendas de produção própria, de terceiros ou anulações de valores",
        "entrada",
        "interestadual",
    ),
    "2201": ("Devolução de venda de produção do estabelecimento", "entrada", "interestadual"),
    "2202": (
        "Devolução de venda de mercadoria adquirida ou recebida de terceiros",
        "entrada",
        "interestadual",
    ),
    "2203": (
        "Devolução de venda de produção do estabelecimento destinada à ZFM ou ALC",
        "entrada",
        "interestadual",
    ),
    "2204": (
        "Devolução de venda de mercadoria adquirida ou recebida de terceiros para ZFM ou ALC",
        "entrada",
        "interestadual",
    ),
    "2205": (
        "Anulação de valor relativo à prestação de serviço de comunicação",
        "entrada",
        "interestadual",
    ),
    "2206": (
        "Anulação de valor relativo à prestação de serviço de transporte",
        "entrada",
        "interestadual",
    ),
    "2207": ("Anulação de valor relativo à venda de energia elétrica", "entrada", "interestadual"),
    "2208": (
        "Devolução de produção do estabelecimento remetida em transferência",
        "entrada",
        "interestadual",
    ),
    "2209": (
        "Devolução de mercadoria adquirida ou recebida de terceiros remetida em transferência",
        "entrada",
        "interestadual",
    ),
    "2250": ("Compras de energia elétrica", "entrada", "interestadual"),
    "2251": (
        "Compra de energia elétrica para distribuição ou comercialização",
        "entrada",
        "interestadual",
    ),
    "2252": (
        "Compra de energia elétrica por estabelecimento industrial",
        "entrada",
        "interestadual",
    ),
    "2253": (
        "Compra de energia elétrica por estabelecimento comercial",
        "entrada",
        "interestadual",
    ),
    "2301": (
        "Aquisição de serviço de comunicação para execução de serviço da mesma natureza",
        "entrada",
        "interestadual",
    ),
    "2302": (
        "Aquisição de serviço de comunicação por estabelecimento industrial",
        "entrada",
        "interestadual",
    ),
    "2303": (
        "Aquisição de serviço de comunicação por estabelecimento comercial",
        "entrada",
        "interestadual",
    ),
    "2401": (
        "Aquisição de serviço de transporte para execução de serviço da mesma natureza",
        "entrada",
        "interestadual",
    ),
    "2403": (
        "Aquisição de serviço de transporte por estabelecimento industrial",
        "entrada",
        "interestadual",
    ),
    "2404": (
        "Aquisição de serviço de transporte por estabelecimento comercial",
        "entrada",
        "interestadual",
    ),
    "2550": (
        "Operações com bens de ativo imobilizado e materiais para uso ou consumo",
        "entrada",
        "interestadual",
    ),
    "2551": ("Compra de bem para o ativo imobilizado", "entrada", "interestadual"),
    "2552": ("Transferência de bem do ativo imobilizado", "entrada", "interestadual"),
    "2553": ("Devolução de venda de bem do ativo imobilizado", "entrada", "interestadual"),
    "2554": (
        "Retorno de bem do ativo imobilizado remetido para uso fora do estabelecimento",
        "entrada",
        "interestadual",
    ),
    "2555": (
        "Entrada de bem do ativo imobilizado de terceiro remetido para uso no estabelecimento",
        "entrada",
        "interestadual",
    ),
    "2556": ("Compra de material para uso ou consumo", "entrada", "interestadual"),
    "2557": ("Transferência de material para uso ou consumo", "entrada", "interestadual"),
    "2900": (
        "Outras entradas de mercadorias ou aquisições de serviços",
        "entrada",
        "interestadual",
    ),
    "2949": (
        "Outra entrada de mercadoria ou prestação de serviço não especificada",
        "entrada",
        "interestadual",
    ),
    # Grupo 3 - Entradas do exterior
    "3100": (
        "Compras para industrialização, produção rural, comercialização ou prestação de serviços",
        "entrada",
        "exterior",
    ),
    "3101": ("Compra para industrialização ou produção rural", "entrada", "exterior"),
    "3102": ("Compra para comercialização", "entrada", "exterior"),
    "3126": (
        "Compra para utilização na prestação de serviço sujeita ao ISSQN",
        "entrada",
        "exterior",
    ),
    "3127": ("Compra para industrialização sob o regime de drawback", "entrada", "exterior"),
    "3201": ("Devolução de venda de produção do estabelecimento", "entrada", "exterior"),
    "3202": (
        "Devolução de venda de mercadoria adquirida ou recebida de terceiros",
        "entrada",
        "exterior",
    ),
    "3211": (
        "Devolução de venda de produção do estabelecimento sob o regime de drawback",
        "entrada",
        "exterior",
    ),
    "3250": ("Compras de energia elétrica", "entrada", "exterior"),
    "3251": (
        "Compra de energia elétrica para distribuição ou comercialização",
        "entrada",
        "exterior",
    ),
    "3301": (
        "Aquisição de serviço de comunicação para execução de serviço da mesma natureza",
        "entrada",
        "exterior",
    ),
    "3401": (
        "Aquisição de serviço de transporte para execução de serviço da mesma natureza",
        "entrada",
        "exterior",
    ),
    "3550": (
        "Operações com bens de ativo imobilizado e materiais para uso ou consumo",
        "entrada",
        "exterior",
    ),
    "3551": ("Compra de bem para o ativo imobilizado", "entrada", "exterior"),
    "3553": ("Devolução de venda de bem do ativo imobilizado", "entrada", "exterior"),
    "3556": ("Compra de material para uso ou consumo", "entrada", "exterior"),
    "3900": ("Outras entradas de mercadorias ou aquisições de serviços", "entrada", "exterior"),
    "3949": (
        "Outra entrada de mercadoria ou prestação de serviço não especificada",
        "entrada",
        "exterior",
    ),
    # Grupo 5 - Saídas estaduais
    "5100": ("Vendas de produção própria ou de terceiros", "saida", "estadual"),
    "5101": ("Venda de produção do estabelecimento", "saida", "estadual"),
    "5102": ("Venda de mercadoria adquirida ou recebida de terceiros", "saida", "estadual"),
    "5103": (
        "Venda de produção do estabelecimento efetuada fora do estabelecimento",
        "saida",
        "estadual",
    ),
    "5104": (
        "Venda de mercadoria adquirida ou recebida de terceiros efetuada fora do estabelecimento",
        "saida",
        "estadual",
    ),
    "5105": (
        "Venda de produção do estabelecimento que não deva por ele transitar",
        "saida",
        "estadual",
    ),
    "5106": (
        "Venda de mercadoria adquirida ou recebida de terceiros que não deva por ele transitar",
        "saida",
        "estadual",
    ),
    "5109": ("Venda de produção do estabelecimento destinada à ZFM ou ALC", "saida", "estadual"),
    "5110": ("Venda de produção do estabelecimento destinada a exportação", "saida", "estadual"),
    "5111": (
        "Venda de produção do estabelecimento remetida anteriormente em consignação mercantil",
        "saida",
        "estadual",
    ),
    "5112": (
        "Venda de mercadoria adquirida ou recebida de terceiros remetida anteriormente em consignação mercantil",
        "saida",
        "estadual",
    ),
    "5113": (
        "Venda de produção do estabelecimento remetida anteriormente em consignação industrial",
        "saida",
        "estadual",
    ),
    "5114": (
        "Venda de mercadoria adquirida ou recebida de terceiros remetida anteriormente em consignação industrial",
        "saida",
        "estadual",
    ),
    "5115": (
        "Venda de mercadoria adquirida ou recebida de terceiros remetida anteriormente em consignação mercantil",
        "saida",
        "estadual",
    ),
    "5116": (
        "Venda de produção do estabelecimento originada de encomenda para recebimento futuro",
        "saida",
        "estadual",
    ),
    "5117": (
        "Venda de mercadoria adquirida ou recebida de terceiros originada de encomenda para recebimento futuro",
        "saida",
        "estadual",
    ),
    "5118": (
        "Venda de produção do estabelecimento entregue ao destinatário pelo depositário",
        "saida",
        "estadual",
    ),
    "5119": (
        "Venda de mercadoria adquirida ou recebida de terceiros entregue ao destinatário pelo depositário",
        "saida",
        "estadual",
    ),
    "5120": (
        "Venda de produção do estabelecimento depositada em depósito fechado ou armazém alfandegado",
        "saida",
        "estadual",
    ),
    "5121": (
        "Venda de mercadoria adquirida ou recebida de terceiros depositada em depósito fechado ou armazém alfandegado",
        "saida",
        "estadual",
    ),
    "5122": (
        "Venda de produção do estabelecimento remetida para industrialização por conta do adquirente",
        "saida",
        "estadual",
    ),
    "5123": (
        "Venda de mercadoria adquirida ou recebida de terceiros remetida para industrialização por conta do adquirente",
        "saida",
        "estadual",
    ),
    "5124": ("Industrialização efetuada para outra empresa", "saida", "estadual"),
    "5125": (
        "Industrialização efetuada para outra empresa quando a mercadoria foi remetida pelo adquirente ao industrializador",
        "saida",
        "estadual",
    ),
    "5150": ("Transferências de produção própria ou de terceiros", "saida", "estadual"),
    "5151": ("Transferência de produção do estabelecimento", "saida", "estadual"),
    "5152": ("Transferência de mercadoria adquirida ou recebida de terceiros", "saida", "estadual"),
    "5153": ("Transferência de energia elétrica", "saida", "estadual"),
    "5154": (
        "Transferência de produção do estabelecimento para atendimento de venda originada de encomenda futura",
        "saida",
        "estadual",
    ),
    "5155": (
        "Transferência de mercadoria adquirida ou recebida de terceiros para atendimento de venda originada de encomenda futura",
        "saida",
        "estadual",
    ),
    "5200": (
        "Devoluções de compras para industrialização, produção rural, comercialização ou anulações de valores",
        "saida",
        "estadual",
    ),
    "5201": ("Devolução de compra para industrialização ou produção rural", "saida", "estadual"),
    "5202": ("Devolução de compra para comercialização", "saida", "estadual"),
    "5205": (
        "Anulação de valor relativo à aquisição de serviço de comunicação",
        "saida",
        "estadual",
    ),
    "5206": (
        "Anulação de valor relativo à aquisição de serviço de transporte",
        "saida",
        "estadual",
    ),
    "5207": ("Anulação de valor relativo à compra de energia elétrica", "saida", "estadual"),
    "5208": (
        "Devolução de mercadoria recebida em transferência para industrialização ou produção rural",
        "saida",
        "estadual",
    ),
    "5209": (
        "Devolução de mercadoria recebida em transferência para comercialização",
        "saida",
        "estadual",
    ),
    "5210": ("Devolução de compra para utilização na prestação de serviço", "saida", "estadual"),
    "5250": ("Vendas de energia elétrica", "saida", "estadual"),
    "5251": ("Venda de energia elétrica para distribuição ou comercialização", "saida", "estadual"),
    "5252": ("Venda de energia elétrica para estabelecimento industrial", "saida", "estadual"),
    "5253": ("Venda de energia elétrica para estabelecimento comercial", "saida", "estadual"),
    "5254": (
        "Venda de energia elétrica para estabelecimento prestador de serviço de transporte",
        "saida",
        "estadual",
    ),
    "5255": (
        "Venda de energia elétrica para estabelecimento prestador de serviço de comunicação",
        "saida",
        "estadual",
    ),
    "5256": (
        "Venda de energia elétrica para estabelecimento de produtor rural",
        "saida",
        "estadual",
    ),
    "5257": ("Venda de energia elétrica para consumo por demanda contratada", "saida", "estadual"),
    "5258": ("Venda de energia elétrica a não contribuinte", "saida", "estadual"),
    "5300": ("Prestações de serviços de comunicação", "saida", "estadual"),
    "5301": (
        "Prestação de serviço de comunicação para execução de serviço da mesma natureza",
        "saida",
        "estadual",
    ),
    "5302": (
        "Prestação de serviço de comunicação a estabelecimento industrial",
        "saida",
        "estadual",
    ),
    "5303": (
        "Prestação de serviço de comunicação a estabelecimento comercial",
        "saida",
        "estadual",
    ),
    "5304": (
        "Prestação de serviço de comunicação a estabelecimento de prestador de serviço de transporte",
        "saida",
        "estadual",
    ),
    "5305": (
        "Prestação de serviço de comunicação a estabelecimento de geradora ou de distribuidora de energia elétrica",
        "saida",
        "estadual",
    ),
    "5306": (
        "Prestação de serviço de comunicação a estabelecimento de produtor rural",
        "saida",
        "estadual",
    ),
    "5307": ("Prestação de serviço de comunicação a não contribuinte", "saida", "estadual"),
    "5351": (
        "Prestação de serviço de transporte para execução de serviço da mesma natureza",
        "saida",
        "estadual",
    ),
    "5352": (
        "Prestação de serviço de transporte a estabelecimento industrial",
        "saida",
        "estadual",
    ),
    "5353": ("Prestação de serviço de transporte a estabelecimento comercial", "saida", "estadual"),
    "5354": (
        "Prestação de serviço de transporte a estabelecimento de prestador de serviço de comunicação",
        "saida",
        "estadual",
    ),
    "5355": (
        "Prestação de serviço de transporte a estabelecimento de geradora ou de distribuidora de energia elétrica",
        "saida",
        "estadual",
    ),
    "5356": (
        "Prestação de serviço de transporte a estabelecimento de produtor rural",
        "saida",
        "estadual",
    ),
    "5357": ("Prestação de serviço de transporte a não contribuinte", "saida", "estadual"),
    "5359": (
        "Prestação de serviço de transporte a contribuinte ou a não contribuinte quando a mercadoria transportada está dispensada de acobertar",
        "saida",
        "estadual",
    ),
    "5400": (
        "Vendas de mercadorias sujeitas ao regime de substituição tributária",
        "saida",
        "estadual",
    ),
    "5401": (
        "Venda de produção do estabelecimento em operações com produto sujeito ao ST",
        "saida",
        "estadual",
    ),
    "5402": (
        "Venda de produção do estabelecimento de produto sujeito ao regime de ST em operação entre contribuintes substitutos do mesmo produto",
        "saida",
        "estadual",
    ),
    "5403": (
        "Venda de mercadoria adquirida ou recebida de terceiros em operação com produto sujeito ao ST",
        "saida",
        "estadual",
    ),
    "5405": (
        "Venda de mercadoria adquirida ou recebida de terceiros com ST já paga",
        "saida",
        "estadual",
    ),
    "5408": (
        "Transferência de produção do estabelecimento em operação com produto sujeito ao ST",
        "saida",
        "estadual",
    ),
    "5409": (
        "Transferência de mercadoria adquirida ou recebida de terceiros em operação com produto sujeito ao ST",
        "saida",
        "estadual",
    ),
    "5410": (
        "Devolução de compra para industrialização em operação com produto sujeito ao ST",
        "saida",
        "estadual",
    ),
    "5411": (
        "Devolução de compra para comercialização em operação com produto sujeito ao ST",
        "saida",
        "estadual",
    ),
    "5500": (
        "Remessas com fim específico de exportação e eventuais devoluções",
        "saida",
        "estadual",
    ),
    "5501": (
        "Remessa de produção do estabelecimento com fim específico de exportação",
        "saida",
        "estadual",
    ),
    "5502": (
        "Remessa de mercadoria adquirida ou recebida de terceiros com fim específico de exportação",
        "saida",
        "estadual",
    ),
    "5503": (
        "Devolução de mercadoria recebida com fim específico de exportação",
        "saida",
        "estadual",
    ),
    "5504": ("Remessa de mercadoria para formação de lote de exportação", "saida", "estadual"),
    "5505": (
        "Remessa de mercadoria, adquirida ou recebida de terceiros, para formação de lote de exportação",
        "saida",
        "estadual",
    ),
    "5550": (
        "Operações com bens de ativo imobilizado e materiais para uso ou consumo",
        "saida",
        "estadual",
    ),
    "5551": ("Venda de bem do ativo imobilizado", "saida", "estadual"),
    "5552": ("Transferência de bem do ativo imobilizado", "saida", "estadual"),
    "5553": ("Devolução de compra de bem para o ativo imobilizado", "saida", "estadual"),
    "5554": (
        "Remessa de bem do ativo imobilizado para uso fora do estabelecimento",
        "saida",
        "estadual",
    ),
    "5555": (
        "Remessa de bem do ativo imobilizado de terceiro remetido para uso no estabelecimento",
        "saida",
        "estadual",
    ),
    "5556": ("Venda de material de uso ou consumo", "saida", "estadual"),
    "5557": ("Transferência de material de uso ou consumo", "saida", "estadual"),
    "5600": ("Créditos e ressarcimentos de ICMS", "saida", "estadual"),
    "5601": ("Transferência de crédito de ICMS acumulado", "saida", "estadual"),
    "5602": (
        "Transferência de saldo credor de ICMS para outro estabelecimento da mesma empresa, destinado à compensação de saldo devedor de ICMS",
        "saida",
        "estadual",
    ),
    "5603": ("Ressarcimento de ICMS retido por ST", "saida", "estadual"),
    "5605": (
        "Transferência de saldo credor de ICMS na entrada de mercadoria do exterior",
        "saida",
        "estadual",
    ),
    "5650": (
        "Saídas de combustíveis, lubrificantes, aditivos e agentes de limpeza",
        "saida",
        "estadual",
    ),
    "5651": (
        "Venda de combustível ou lubrificante de produção do estabelecimento destinado à industrialização",
        "saida",
        "estadual",
    ),
    "5652": (
        "Venda de combustível ou lubrificante de produção do estabelecimento destinado à comercialização",
        "saida",
        "estadual",
    ),
    "5653": (
        "Venda de combustível ou lubrificante de produção do estabelecimento destinado a consumidor ou usuário final",
        "saida",
        "estadual",
    ),
    "5654": (
        "Venda de combustível ou lubrificante adquirido ou recebido de terceiros destinado à industrialização",
        "saida",
        "estadual",
    ),
    "5655": (
        "Venda de combustível ou lubrificante adquirido ou recebido de terceiros destinado à comercialização",
        "saida",
        "estadual",
    ),
    "5656": (
        "Venda de combustível ou lubrificante adquirido ou recebido de terceiros destinado a consumidor ou usuário final",
        "saida",
        "estadual",
    ),
    "5657": (
        "Remessa de combustível ou lubrificante adquirido ou recebido de terceiros para venda fora do estabelecimento",
        "saida",
        "estadual",
    ),
    "5658": (
        "Transferência de combustível ou lubrificante de produção do estabelecimento",
        "saida",
        "estadual",
    ),
    "5659": (
        "Transferência de combustível ou lubrificante adquirido ou recebido de terceiros",
        "saida",
        "estadual",
    ),
    "5660": (
        "Devolução de compra de combustível ou lubrificante adquirido para industrialização",
        "saida",
        "estadual",
    ),
    "5661": (
        "Devolução de compra de combustível ou lubrificante adquirido para comercialização",
        "saida",
        "estadual",
    ),
    "5662": (
        "Devolução de compra de combustível ou lubrificante adquirido por consumidor ou usuário final",
        "saida",
        "estadual",
    ),
    "5900": ("Outras saídas de mercadorias ou prestações de serviços", "saida", "estadual"),
    "5901": (
        "Remessa para industrialização por conta e ordem do adquirente da mercadoria, quando esta não transitar pelo estabelecimento do adquirente",
        "saida",
        "estadual",
    ),
    "5902": (
        "Retorno de mercadoria utilizada na industrialização por conta e ordem do adquirente da mercadoria",
        "saida",
        "estadual",
    ),
    "5903": (
        "Retorno de mercadoria recebida para industrialização e não aplicada no referido processo",
        "saida",
        "estadual",
    ),
    "5904": ("Remessa para venda fora do estabelecimento", "saida", "estadual"),
    "5905": ("Remessa para depósito fechado ou armazém alfandegado", "saida", "estadual"),
    "5906": (
        "Retorno de mercadoria depositada em depósito fechado ou armazém alfandegado",
        "saida",
        "estadual",
    ),
    "5907": (
        "Retorno simbólico de mercadoria depositada em depósito fechado ou armazém alfandegado",
        "saida",
        "estadual",
    ),
    "5908": ("Remessa de bem por conta de contrato de comodato", "saida", "estadual"),
    "5909": ("Retorno de bem remetido por conta de contrato de comodato", "saida", "estadual"),
    "5910": ("Remessa em bonificação, doação ou brinde", "saida", "estadual"),
    "5911": ("Remessa de amostra grátis", "saida", "estadual"),
    "5912": ("Remessa de mercadoria ou bem para demonstração", "saida", "estadual"),
    "5913": ("Retorno de mercadoria ou bem recebido para demonstração", "saida", "estadual"),
    "5914": ("Remessa de mercadoria ou bem para exposição ou feira", "saida", "estadual"),
    "5915": ("Remessa de mercadoria ou bem para conserto ou reparo", "saida", "estadual"),
    "5916": ("Retorno de mercadoria ou bem recebido para conserto ou reparo", "saida", "estadual"),
    "5917": ("Remessa de mercadoria em consignação mercantil ou industrial", "saida", "estadual"),
    "5918": (
        "Devolução de mercadoria recebida em consignação mercantil ou industrial",
        "saida",
        "estadual",
    ),
    "5919": (
        "Devolução simbólica de mercadoria vendida ou utilizada em processo industrial, remetida anteriormente em consignação mercantil ou industrial",
        "saida",
        "estadual",
    ),
    "5920": ("Remessa de vasilhame ou sacaria", "saida", "estadual"),
    "5921": ("Retorno de vasilhame ou sacaria", "saida", "estadual"),
    "5922": (
        "Lançamento efetuado a título de simples faturamento decorrente de venda para entrega futura",
        "saida",
        "estadual",
    ),
    "5923": (
        "Remessa de mercadoria por conta e ordem de terceiros, em venda à ordem",
        "saida",
        "estadual",
    ),
    "5924": (
        "Remessa para reconhecimento de crédito de estoque fiscal de ICMS",
        "saida",
        "estadual",
    ),
    "5925": (
        "Retorno de mercadoria depositada em depósito fechado ou armazém alfandegado, exceto campo específico",
        "saida",
        "estadual",
    ),
    "5926": (
        "Lançamento efetuado a título de reclassificação de mercadoria decorrente de formação de kit",
        "saida",
        "estadual",
    ),
    "5949": (
        "Outra saída de mercadoria ou prestação de serviço não especificada",
        "saida",
        "estadual",
    ),
    # Grupo 6 - Saídas interestaduais
    "6100": ("Vendas de produção própria ou de terceiros", "saida", "interestadual"),
    "6101": ("Venda de produção do estabelecimento", "saida", "interestadual"),
    "6102": ("Venda de mercadoria adquirida ou recebida de terceiros", "saida", "interestadual"),
    "6103": (
        "Venda de produção do estabelecimento efetuada fora do estabelecimento",
        "saida",
        "interestadual",
    ),
    "6104": (
        "Venda de mercadoria adquirida ou recebida de terceiros efetuada fora do estabelecimento",
        "saida",
        "interestadual",
    ),
    "6105": (
        "Venda de produção do estabelecimento que não deva por ele transitar",
        "saida",
        "interestadual",
    ),
    "6106": (
        "Venda de mercadoria adquirida ou recebida de terceiros que não deva por ele transitar",
        "saida",
        "interestadual",
    ),
    "6107": (
        "Venda de produção do estabelecimento destinada à Zona Franca de Manaus",
        "saida",
        "interestadual",
    ),
    "6108": (
        "Venda de produção do estabelecimento destinada a exportação",
        "saida",
        "interestadual",
    ),
    "6109": (
        "Venda de produção do estabelecimento destinada à ZFM ou ALC",
        "saida",
        "interestadual",
    ),
    "6110": (
        "Venda de produção do estabelecimento destinada a exportação",
        "saida",
        "interestadual",
    ),
    "6116": (
        "Venda de produção do estabelecimento originada de encomenda para recebimento futuro",
        "saida",
        "interestadual",
    ),
    "6117": (
        "Venda de mercadoria adquirida ou recebida de terceiros originada de encomenda para recebimento futuro",
        "saida",
        "interestadual",
    ),
    "6120": (
        "Venda de produção do estabelecimento em venda à ordem, já recebida do fornecedor remetente",
        "saida",
        "interestadual",
    ),
    "6121": (
        "Venda de mercadoria adquirida ou recebida de terceiros em venda à ordem, já recebida do fornecedor remetente",
        "saida",
        "interestadual",
    ),
    "6122": (
        "Venda de produção do estabelecimento remetida para industrialização por conta do adquirente",
        "saida",
        "interestadual",
    ),
    "6123": (
        "Venda de mercadoria adquirida ou recebida de terceiros remetida para industrialização por conta do adquirente",
        "saida",
        "interestadual",
    ),
    "6124": ("Industrialização efetuada para outra empresa", "saida", "interestadual"),
    "6125": (
        "Industrialização efetuada para outra empresa quando a mercadoria foi remetida pelo adquirente ao industrializador",
        "saida",
        "interestadual",
    ),
    "6150": ("Transferências de produção própria ou de terceiros", "saida", "interestadual"),
    "6151": ("Transferência de produção do estabelecimento", "saida", "interestadual"),
    "6152": (
        "Transferência de mercadoria adquirida ou recebida de terceiros",
        "saida",
        "interestadual",
    ),
    "6153": ("Transferência de energia elétrica", "saida", "interestadual"),
    "6155": (
        "Transferência de mercadoria adquirida ou recebida de terceiros para atendimento de venda originada de encomenda futura",
        "saida",
        "interestadual",
    ),
    "6201": (
        "Devolução de compra para industrialização ou produção rural",
        "saida",
        "interestadual",
    ),
    "6202": ("Devolução de compra para comercialização", "saida", "interestadual"),
    "6205": (
        "Anulação de valor relativo à aquisição de serviço de comunicação",
        "saida",
        "interestadual",
    ),
    "6206": (
        "Anulação de valor relativo à aquisição de serviço de transporte",
        "saida",
        "interestadual",
    ),
    "6207": ("Anulação de valor relativo à compra de energia elétrica", "saida", "interestadual"),
    "6210": (
        "Devolução de compra para utilização na prestação de serviço",
        "saida",
        "interestadual",
    ),
    "6250": ("Vendas de energia elétrica", "saida", "interestadual"),
    "6251": (
        "Venda de energia elétrica para distribuição ou comercialização",
        "saida",
        "interestadual",
    ),
    "6252": ("Venda de energia elétrica para estabelecimento industrial", "saida", "interestadual"),
    "6253": ("Venda de energia elétrica para estabelecimento comercial", "saida", "interestadual"),
    "6301": (
        "Prestação de serviço de comunicação para execução de serviço da mesma natureza",
        "saida",
        "interestadual",
    ),
    "6302": (
        "Prestação de serviço de comunicação a estabelecimento industrial",
        "saida",
        "interestadual",
    ),
    "6351": (
        "Prestação de serviço de transporte para execução de serviço da mesma natureza",
        "saida",
        "interestadual",
    ),
    "6352": (
        "Prestação de serviço de transporte a estabelecimento industrial",
        "saida",
        "interestadual",
    ),
    "6353": (
        "Prestação de serviço de transporte a estabelecimento comercial",
        "saida",
        "interestadual",
    ),
    "6354": (
        "Prestação de serviço de transporte a estabelecimento de prestador de serviço de comunicação",
        "saida",
        "interestadual",
    ),
    "6355": (
        "Prestação de serviço de transporte a estabelecimento de geradora ou de distribuidora de energia elétrica",
        "saida",
        "interestadual",
    ),
    "6356": (
        "Prestação de serviço de transporte a estabelecimento de produtor rural",
        "saida",
        "interestadual",
    ),
    "6357": ("Prestação de serviço de transporte a não contribuinte", "saida", "interestadual"),
    "6401": (
        "Venda de produção do estabelecimento em operação com produto sujeito ao ST para outro estado",
        "saida",
        "interestadual",
    ),
    "6402": (
        "Venda de produção do estabelecimento de produto sujeito ao ST em operação entre contribuintes substitutos",
        "saida",
        "interestadual",
    ),
    "6403": (
        "Venda de mercadoria adquirida ou recebida de terceiros em operação com produto sujeito ao ST para outro estado",
        "saida",
        "interestadual",
    ),
    "6404": (
        "Venda de mercadoria sujeita ao ST cujo imposto já tenha sido retido para outro estado",
        "saida",
        "interestadual",
    ),
    "6408": (
        "Transferência de produção do estabelecimento em operação com produto sujeito ao ST",
        "saida",
        "interestadual",
    ),
    "6409": (
        "Transferência de mercadoria adquirida ou recebida de terceiros em operação com produto sujeito ao ST",
        "saida",
        "interestadual",
    ),
    "6410": (
        "Devolução de compra para industrialização em operação com produto sujeito ao ST",
        "saida",
        "interestadual",
    ),
    "6411": (
        "Devolução de compra para comercialização em operação com produto sujeito ao ST",
        "saida",
        "interestadual",
    ),
    "6501": (
        "Remessa de produção do estabelecimento com fim específico de exportação",
        "saida",
        "interestadual",
    ),
    "6502": (
        "Remessa de mercadoria adquirida ou recebida de terceiros com fim específico de exportação",
        "saida",
        "interestadual",
    ),
    "6503": (
        "Devolução de mercadoria recebida com fim específico de exportação",
        "saida",
        "interestadual",
    ),
    "6504": ("Remessa de mercadoria para formação de lote de exportação", "saida", "interestadual"),
    "6505": (
        "Remessa de mercadoria, adquirida ou recebida de terceiros, para formação de lote de exportação",
        "saida",
        "interestadual",
    ),
    "6550": (
        "Operações com bens de ativo imobilizado e materiais para uso ou consumo",
        "saida",
        "interestadual",
    ),
    "6551": ("Venda de bem do ativo imobilizado", "saida", "interestadual"),
    "6552": ("Transferência de bem do ativo imobilizado", "saida", "interestadual"),
    "6553": ("Devolução de compra de bem para o ativo imobilizado", "saida", "interestadual"),
    "6554": (
        "Remessa de bem do ativo imobilizado para uso fora do estabelecimento",
        "saida",
        "interestadual",
    ),
    "6555": (
        "Remessa de bem do ativo imobilizado de terceiro remetido para uso no estabelecimento",
        "saida",
        "interestadual",
    ),
    "6556": ("Venda de material de uso ou consumo", "saida", "interestadual"),
    "6557": ("Transferência de material de uso ou consumo", "saida", "interestadual"),
    "6901": (
        "Remessa para industrialização por conta e ordem do adquirente",
        "saida",
        "interestadual",
    ),
    "6902": (
        "Retorno de mercadoria utilizada na industrialização por conta e ordem do adquirente",
        "saida",
        "interestadual",
    ),
    "6903": (
        "Retorno de mercadoria recebida para industrialização e não aplicada no referido processo",
        "saida",
        "interestadual",
    ),
    "6904": ("Remessa para venda fora do estabelecimento", "saida", "interestadual"),
    "6905": ("Remessa para depósito fechado ou armazém alfandegado", "saida", "interestadual"),
    "6906": (
        "Retorno de mercadoria depositada em depósito fechado ou armazém alfandegado",
        "saida",
        "interestadual",
    ),
    "6910": ("Remessa em bonificação, doação ou brinde", "saida", "interestadual"),
    "6911": ("Remessa de amostra grátis", "saida", "interestadual"),
    "6912": ("Remessa de mercadoria ou bem para demonstração", "saida", "interestadual"),
    "6913": ("Retorno de mercadoria ou bem recebido para demonstração", "saida", "interestadual"),
    "6915": ("Remessa de mercadoria ou bem para conserto ou reparo", "saida", "interestadual"),
    "6916": (
        "Retorno de mercadoria ou bem recebido para conserto ou reparo",
        "saida",
        "interestadual",
    ),
    "6917": (
        "Remessa de mercadoria em consignação mercantil ou industrial",
        "saida",
        "interestadual",
    ),
    "6918": (
        "Devolução de mercadoria recebida em consignação mercantil ou industrial",
        "saida",
        "interestadual",
    ),
    "6920": ("Remessa de vasilhame ou sacaria", "saida", "interestadual"),
    "6921": ("Retorno de vasilhame ou sacaria", "saida", "interestadual"),
    "6922": (
        "Lançamento efetuado a título de simples faturamento decorrente de venda para entrega futura",
        "saida",
        "interestadual",
    ),
    "6923": (
        "Remessa de mercadoria por conta e ordem de terceiros, em venda à ordem",
        "saida",
        "interestadual",
    ),
    "6949": (
        "Outra saída de mercadoria ou prestação de serviço não especificada",
        "saida",
        "interestadual",
    ),
    # Grupo 7 - Saídas para o exterior
    "7100": ("Vendas de produção própria ou de terceiros", "saida", "exterior"),
    "7101": ("Exportação de produção do estabelecimento", "saida", "exterior"),
    "7102": ("Exportação de mercadoria adquirida ou recebida de terceiros", "saida", "exterior"),
    "7105": (
        "Exportação de produção do estabelecimento que não deva por ele transitar",
        "saida",
        "exterior",
    ),
    "7106": (
        "Exportação de mercadoria adquirida ou recebida de terceiros que não deva por ele transitar",
        "saida",
        "exterior",
    ),
    "7127": ("Venda de produção do estabelecimento sob o regime de drawback", "saida", "exterior"),
    "7201": ("Devolução de compra para industrialização", "saida", "exterior"),
    "7202": ("Devolução de compra para comercialização", "saida", "exterior"),
    "7210": ("Devolução de compra para utilização na prestação de serviço", "saida", "exterior"),
    "7211": (
        "Devolução de compra para industrialização sob o regime de drawback",
        "saida",
        "exterior",
    ),
    "7501": (
        "Exportação de mercadoria recebida com fim específico de exportação",
        "saida",
        "exterior",
    ),
    "7550": ("Operações com bens de ativo imobilizado", "saida", "exterior"),
    "7551": ("Exportação de bem do ativo imobilizado", "saida", "exterior"),
    "7900": ("Outras saídas de mercadorias ou prestações de serviços", "saida", "exterior"),
    "7949": (
        "Outra saída de mercadoria ou prestação de serviço não especificada",
        "saida",
        "exterior",
    ),
}

# ---------------------------------------------------------------------------
# CST - Código de Situação Tributária
# ---------------------------------------------------------------------------

# CST ICMS - regime normal (Lucro Real/Presumido): código = origem (1 dígito) + tributação (2 dígitos)
CST_ICMS_NORMAL: dict[str, str] = {
    "000": "Nacional - Tributada integralmente",
    "010": "Nacional - Tributada e com cobrança do ICMS por substituição tributária",
    "020": "Nacional - Com redução de base de cálculo",
    "030": "Nacional - Isenta ou não tributada e com cobrança do ICMS por substituição tributária",
    "040": "Nacional - Isenta",
    "041": "Nacional - Não tributada",
    "050": "Nacional - Suspensão",
    "051": "Nacional - Diferimento",
    "060": "Nacional - ICMS cobrado anteriormente por substituição tributária",
    "070": "Nacional - Com redução da base de cálculo e cobrança do ICMS por ST",
    "090": "Nacional - Outras",
    "100": "Estrangeira (importação direta) - Tributada integralmente",
    "110": "Estrangeira (importação direta) - Tributada e com cobrança do ICMS por ST",
    "120": "Estrangeira (importação direta) - Com redução de base de cálculo",
    "130": "Estrangeira (importação direta) - Isenta ou não tributada e com cobrança do ICMS por ST",
    "140": "Estrangeira (importação direta) - Isenta",
    "141": "Estrangeira (importação direta) - Não tributada",
    "150": "Estrangeira (importação direta) - Suspensão",
    "151": "Estrangeira (importação direta) - Diferimento",
    "160": "Estrangeira (importação direta) - ICMS cobrado anteriormente por ST",
    "170": "Estrangeira (importação direta) - Com redução da BC e cobrança do ICMS por ST",
    "190": "Estrangeira (importação direta) - Outras",
    "200": "Estrangeira (mercado interno) - Tributada integralmente",
    "210": "Estrangeira (mercado interno) - Tributada e com cobrança do ICMS por ST",
    "220": "Estrangeira (mercado interno) - Com redução de base de cálculo",
    "230": "Estrangeira (mercado interno) - Isenta ou não tributada e com cobrança do ICMS por ST",
    "240": "Estrangeira (mercado interno) - Isenta",
    "241": "Estrangeira (mercado interno) - Não tributada",
    "250": "Estrangeira (mercado interno) - Suspensão",
    "251": "Estrangeira (mercado interno) - Diferimento",
    "260": "Estrangeira (mercado interno) - ICMS cobrado anteriormente por ST",
    "270": "Estrangeira (mercado interno) - Com redução da BC e cobrança do ICMS por ST",
    "290": "Estrangeira (mercado interno) - Outras",
    "300": "Nacional com > 40% de conteúdo de importação - Tributada integralmente",
    "310": "Nacional com > 40% de conteúdo de importação - Tributada e com cobrança do ICMS por ST",
    "320": "Nacional com > 40% de conteúdo de importação - Com redução de base de cálculo",
    "330": "Nacional com > 40% de conteúdo de importação - Isenta ou não tributada com cobrança do ICMS por ST",
    "340": "Nacional com > 40% de conteúdo de importação - Isenta",
    "341": "Nacional com > 40% de conteúdo de importação - Não tributada",
    "350": "Nacional com > 40% de conteúdo de importação - Suspensão",
    "351": "Nacional com > 40% de conteúdo de importação - Diferimento",
    "360": "Nacional com > 40% de conteúdo de importação - ICMS cobrado anteriormente por ST",
    "370": "Nacional com > 40% de conteúdo de importação - Com redução da BC e cobrança do ICMS por ST",
    "390": "Nacional com > 40% de conteúdo de importação - Outras",
    "400": "Nacional com processo produtivo básico - Tributada integralmente",
    "410": "Nacional com processo produtivo básico - Tributada e com cobrança do ICMS por ST",
    "420": "Nacional com processo produtivo básico - Com redução de base de cálculo",
    "430": "Nacional com processo produtivo básico - Isenta ou não tributada com cobrança do ICMS por ST",
    "440": "Nacional com processo produtivo básico - Isenta",
    "441": "Nacional com processo produtivo básico - Não tributada",
    "450": "Nacional com processo produtivo básico - Suspensão",
    "451": "Nacional com processo produtivo básico - Diferimento",
    "460": "Nacional com processo produtivo básico - ICMS cobrado anteriormente por ST",
    "470": "Nacional com processo produtivo básico - Com redução da BC e cobrança do ICMS por ST",
    "490": "Nacional com processo produtivo básico - Outras",
    "500": "Nacional com < 40% de conteúdo de importação - Tributada integralmente",
    "510": "Nacional com < 40% de conteúdo de importação - Tributada e com cobrança do ICMS por ST",
    "520": "Nacional com < 40% de conteúdo de importação - Com redução de base de cálculo",
    "530": "Nacional com < 40% de conteúdo de importação - Isenta ou não tributada com cobrança do ICMS por ST",
    "540": "Nacional com < 40% de conteúdo de importação - Isenta",
    "541": "Nacional com < 40% de conteúdo de importação - Não tributada",
    "550": "Nacional com < 40% de conteúdo de importação - Suspensão",
    "551": "Nacional com < 40% de conteúdo de importação - Diferimento",
    "560": "Nacional com < 40% de conteúdo de importação - ICMS cobrado anteriormente por ST",
    "570": "Nacional com < 40% de conteúdo de importação - Com redução da BC e cobrança do ICMS por ST",
    "590": "Nacional com < 40% de conteúdo de importação - Outras",
    "600": "Estrangeira (importação direta) sem similar nacional - Tributada integralmente",
    "610": "Estrangeira (importação direta) sem similar nacional - Tributada e com cobrança do ICMS por ST",
    "620": "Estrangeira (importação direta) sem similar nacional - Com redução de base de cálculo",
    "630": "Estrangeira (importação direta) sem similar nacional - Isenta ou não tributada com cobrança do ICMS por ST",
    "640": "Estrangeira (importação direta) sem similar nacional - Isenta",
    "641": "Estrangeira (importação direta) sem similar nacional - Não tributada",
    "650": "Estrangeira (importação direta) sem similar nacional - Suspensão",
    "651": "Estrangeira (importação direta) sem similar nacional - Diferimento",
    "660": "Estrangeira (importação direta) sem similar nacional - ICMS cobrado anteriormente por ST",
    "670": "Estrangeira (importação direta) sem similar nacional - Com redução da BC e cobrança do ICMS por ST",
    "690": "Estrangeira (importação direta) sem similar nacional - Outras",
    "700": "Estrangeira (mercado interno) sem similar nacional - Tributada integralmente",
    "710": "Estrangeira (mercado interno) sem similar nacional - Tributada e com cobrança do ICMS por ST",
    "720": "Estrangeira (mercado interno) sem similar nacional - Com redução de base de cálculo",
    "730": "Estrangeira (mercado interno) sem similar nacional - Isenta ou não tributada com cobrança do ICMS por ST",
    "740": "Estrangeira (mercado interno) sem similar nacional - Isenta",
    "741": "Estrangeira (mercado interno) sem similar nacional - Não tributada",
    "750": "Estrangeira (mercado interno) sem similar nacional - Suspensão",
    "751": "Estrangeira (mercado interno) sem similar nacional - Diferimento",
    "760": "Estrangeira (mercado interno) sem similar nacional - ICMS cobrado anteriormente por ST",
    "770": "Estrangeira (mercado interno) sem similar nacional - Com redução da BC e cobrança do ICMS por ST",
    "790": "Estrangeira (mercado interno) sem similar nacional - Outras",
    "800": "Nacional com > 70% de conteúdo de importação - Tributada integralmente",
    "810": "Nacional com > 70% de conteúdo de importação - Tributada e com cobrança do ICMS por ST",
    "820": "Nacional com > 70% de conteúdo de importação - Com redução de base de cálculo",
    "830": "Nacional com > 70% de conteúdo de importação - Isenta ou não tributada com cobrança do ICMS por ST",
    "840": "Nacional com > 70% de conteúdo de importação - Isenta",
    "841": "Nacional com > 70% de conteúdo de importação - Não tributada",
    "850": "Nacional com > 70% de conteúdo de importação - Suspensão",
    "851": "Nacional com > 70% de conteúdo de importação - Diferimento",
    "860": "Nacional com > 70% de conteúdo de importação - ICMS cobrado anteriormente por ST",
    "870": "Nacional com > 70% de conteúdo de importação - Com redução da BC e cobrança do ICMS por ST",
    "890": "Nacional com > 70% de conteúdo de importação - Outras",
}

# CSOSN - Código de Situação da Operação no Simples Nacional (Resolução CGSN 94/2011)
CSOSN_TABLE: dict[str, str] = {
    "101": "Tributada pelo Simples Nacional com permissão de crédito",
    "102": "Tributada pelo Simples Nacional sem permissão de crédito",
    "103": "Isenção do ICMS no Simples Nacional para faixa de receita bruta",
    "201": "Tributada pelo Simples Nacional com permissão de crédito e com cobrança do ICMS por ST",
    "202": "Tributada pelo Simples Nacional sem permissão de crédito e com cobrança do ICMS por ST",
    "203": "Isenção do ICMS no Simples Nacional para faixa de receita bruta e com cobrança do ICMS por ST",
    "300": "Imune",
    "400": "Não tributada pelo Simples Nacional",
    "500": "ICMS cobrado anteriormente por ST ou por antecipação",
    "900": "Outros",
}

# CST PIS/COFINS (IN SRF 247/2002, Tabela 4.3.3 e 4.3.4 do SPED)
CST_PIS_COFINS: dict[str, str] = {
    "01": "Operação tributável - base de cálculo = valor da operação (alíquota normal)",
    "02": "Operação tributável - base de cálculo = valor da operação (alíquota diferenciada)",
    "03": "Operação tributável - base de cálculo = quantidade vendida x alíquota por unidade",
    "04": "Operação tributável - tributação monofásica (alíquota zero para o revendedor)",
    "05": "Operação tributável - substituição tributária",
    "06": "Operação tributável - alíquota zero",
    "07": "Operação isenta da contribuição",
    "08": "Operação sem incidência da contribuição",
    "09": "Operação com suspensão da contribuição",
    "49": "Outras operações de saída",
    "50": "Operação com direito a crédito - vinculada exclusivamente a receita tributada no mercado interno",
    "51": "Operação com direito a crédito - vinculada exclusivamente a receita não tributada no mercado interno",
    "52": "Operação com direito a crédito - vinculada exclusivamente a receita de exportação",
    "53": "Operação com direito a crédito - vinculada a receitas tributadas e não tributadas no mercado interno",
    "54": "Operação com direito a crédito - vinculada a receitas tributadas no mercado interno e de exportação",
    "55": "Operação com direito a crédito - vinculada a receitas não tributadas no mercado interno e de exportação",
    "56": "Operação com direito a crédito - vinculada a receitas tributadas e não tributadas e de exportação",
    "60": "Crédito presumido - operação de aquisição vinculada exclusivamente a receita tributada no mercado interno",
    "61": "Crédito presumido - operação de aquisição vinculada exclusivamente a receita não tributada no mercado interno",
    "62": "Crédito presumido - operação de aquisição vinculada exclusivamente a receita de exportação",
    "63": "Crédito presumido - operação de aquisição vinculada a receitas tributadas e não tributadas no mercado interno",
    "64": "Crédito presumido - operação de aquisição vinculada a receitas tributadas no mercado interno e de exportação",
    "65": "Crédito presumido - operação de aquisição vinculada a receitas não tributadas no mercado interno e de exportação",
    "66": "Crédito presumido - operação de aquisição vinculada a receitas tributadas e não tributadas e de exportação",
    "67": "Crédito presumido - outras operações",
    "70": "Operação de aquisição sem direito a crédito",
    "71": "Operação de aquisição com isenção",
    "72": "Operação de aquisição com suspensão",
    "73": "Operação de aquisição com alíquota zero",
    "74": "Operação de aquisição sem incidência da contribuição",
    "75": "Operação de aquisição por ST",
    "98": "Outras operações de entrada",
    "99": "Outras operações",
}

# CST IPI (Tabela Anexo à IN SRF 422/2004)
CST_IPI_ENTRADA: dict[str, str] = {
    "00": "Entrada com recuperação de crédito",
    "01": "Entrada tributada com alíquota zero",
    "02": "Entrada isenta",
    "03": "Entrada não tributada",
    "04": "Entrada imune",
    "05": "Entrada com suspensão",
    "49": "Outras entradas",
}

CST_IPI_SAIDA: dict[str, str] = {
    "50": "Saída tributada",
    "51": "Saída tributável com alíquota zero",
    "52": "Saída isenta",
    "53": "Saída não tributada",
    "54": "Saída imune",
    "55": "Saída com suspensão",
    "99": "Outras saídas",
}

# ---------------------------------------------------------------------------
# ICMS - Alíquotas interestaduais e internas (EC 87/2015, Resolução SF 22/2008)
# ---------------------------------------------------------------------------

# Alíquotas internas do ICMS por UF (valores predominantes para cálculo do DIFAL)
# Fonte: legislação estadual compilada (CONFAZ/SEFAZ estaduais)
# AVISO: alíquotas internas podem variar por produto/operação; estes são os valores
# gerais de referência. Consultar a legislação estadual específica para cada caso.
ICMS_ALIQUOTA_INTERNA: dict[str, float] = {
    "AC": 17.0,
    "AL": 19.0,
    "AM": 20.0,
    "AP": 18.0,
    "BA": 19.5,
    "CE": 20.0,
    "DF": 20.0,
    "ES": 17.0,
    "GO": 19.0,
    "MA": 22.0,
    "MT": 17.0,
    "MS": 17.0,
    "MG": 18.0,
    "PA": 19.0,
    "PB": 20.0,
    "PR": 19.5,
    "PE": 20.5,
    "PI": 21.0,
    "RJ": 22.0,
    "RN": 20.0,
    "RS": 17.5,
    "RO": 19.5,
    "RR": 20.0,
    "SC": 17.0,
    "SP": 18.0,
    "SE": 19.0,
    "TO": 20.0,
}

# UFs do Norte, Nordeste e Centro-Oeste (recebem 12% nas operações interestaduais)
# demais UFs (Sul, Sudeste exceto ES) recebem 7% ou 12% dependendo da origem
_UFS_12_PERCENT = {
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "GO",
    "MA",
    "MT",
    "MS",
    "PA",
    "PB",
    "PE",
    "PI",
    "RN",
    "RO",
    "RR",
    "SE",
    "TO",
}
# UFs de origem que enviam à alíquota de 7% para as UFs não listadas acima (Sul e Sudeste)
_UFS_ORIGEM_7_PERCENT_PARA_SUL_SUDESTE = {"MG", "PR", "RS", "SC", "SP", "RJ", "ES"}

# Nota: ZFM (AM) em operações para SP recebe 12%; ES tem tratamento equiparado às demais


def _calcular_aliquota_interestadual(uf_origem: str, uf_destino: str) -> float:
    """
    Calcula a alíquota interestadual do ICMS conforme Resolução SF 22/2008.

    Regra:
    - 4%: operações com bens importados (Resolução SF 13/2012) - NÃO tratado aqui.
    - 7%: operações entre contribuintes de SP, MG, PR, RS, SC, RJ, ES para contribuintes
          de SP, MG, PR, RS, SC, RJ, ES.
    - 12%: demais operações interestaduais.
    """
    if uf_destino in _UFS_12_PERCENT:
        return 12.0
    if uf_origem in _UFS_ORIGEM_7_PERCENT_PARA_SUL_SUDESTE:
        return 7.0
    return 12.0


# ---------------------------------------------------------------------------
# NCM/CEST - SQLite bundled
# ---------------------------------------------------------------------------

_DB_PATH: Path | None = None
_DB_CONN: sqlite3.Connection | None = None


def _get_db_path() -> Path:
    """Retorna o caminho do banco SQLite bundled."""
    global _DB_PATH
    if _DB_PATH is None:
        try:
            # Tenta localizar via importlib.resources (instalado como pacote)
            ref = importlib.resources.files("mcp_fiscal_brasil.tabelas.data").joinpath(
                "tabelas_fiscais.db"
            )
            _DB_PATH = Path(str(ref))
        except (TypeError, FileNotFoundError):
            # Fallback: caminho relativo ao módulo (desenvolvimento local)
            _DB_PATH = Path(__file__).parent / "data" / "tabelas_fiscais.db"
    return _DB_PATH


def _get_conn() -> sqlite3.Connection | None:
    """Retorna a conexão SQLite, inicializando se necessário. Retorna None se DB não existir."""
    global _DB_CONN
    if _DB_CONN is not None:
        return _DB_CONN

    db_path = _get_db_path()
    if not db_path.exists():
        logger.warning(
            "tabelas_db_not_found",
            path=str(db_path),
            hint="Execute: python scripts/build_tabelas_db.py para gerar o banco.",
        )
        return None

    _DB_CONN = sqlite3.connect(str(db_path), check_same_thread=False)
    _DB_CONN.row_factory = sqlite3.Row
    logger.info("tabelas_db_connected", path=str(db_path))
    return _DB_CONN


# ---------------------------------------------------------------------------
# Funções públicas de consulta
# ---------------------------------------------------------------------------


def buscar_cfop(codigo: str) -> dict[str, Any] | None:
    """Retorna dados do CFOP ou None se não encontrado."""
    codigo_limpo = codigo.strip().lstrip("0")
    # Normaliza: CFOP pode vir como "5102" ou "5.102"
    codigo_norm = codigo.replace(".", "").strip()
    dado = CFOP_TABLE.get(codigo_norm)
    if dado is None:
        # Tenta com zero à esquerda removido e recomposto
        dado = CFOP_TABLE.get(codigo_limpo.zfill(4))
    if dado is None:
        return None
    descricao, tipo, aplicacao = dado
    grupo = codigo_norm[0] if codigo_norm else ""
    return {
        "codigo": codigo_norm,
        "descricao": descricao,
        "tipo": tipo,
        "aplicacao": aplicacao,
        "grupo": grupo,
    }


def validar_cst(cst: str, regime: str) -> dict[str, Any]:
    """
    Valida um código CST ou CSOSN conforme o regime tributário.

    Args:
        cst: Código CST/CSOSN a validar.
        regime: 'normal' (Lucro Real/Presumido) ou 'simples' (Simples Nacional).

    Returns:
        Dicionário com valido, descricao, regime e tabela.
    """
    cst_upper = cst.strip().upper()
    regime_lower = regime.strip().lower()

    if regime_lower == "simples":
        # CSOSN para Simples Nacional
        desc = CSOSN_TABLE.get(cst_upper)
        if desc:
            return {
                "cst": cst_upper,
                "valido": True,
                "descricao": desc,
                "regime": "simples",
                "tabela": "CSOSN",
            }
        # Tenta PIS/COFINS e IPI (também usados no Simples para documentos específicos)
        for tabela, dados in [
            ("CST_PIS_COFINS", CST_PIS_COFINS),
            ("CST_IPI_ENTRADA", CST_IPI_ENTRADA),
            ("CST_IPI_SAIDA", CST_IPI_SAIDA),
        ]:
            if cst_upper in dados:
                return {
                    "cst": cst_upper,
                    "valido": True,
                    "descricao": dados[cst_upper],
                    "regime": "simples",
                    "tabela": tabela,
                }
        return {
            "cst": cst_upper,
            "valido": False,
            "descricao": None,
            "regime": "simples",
            "tabela": None,
        }

    # Regime normal: Lucro Real, Presumido, Arbitrado
    # CST ICMS (3 dígitos)
    if len(cst_upper) == 3:
        desc = CST_ICMS_NORMAL.get(cst_upper)
        if desc:
            return {
                "cst": cst_upper,
                "valido": True,
                "descricao": desc,
                "regime": "normal",
                "tabela": "CST_ICMS",
            }
    # CST PIS/COFINS (2 dígitos)
    if len(cst_upper) == 2:
        desc = CST_PIS_COFINS.get(cst_upper)
        if desc:
            return {
                "cst": cst_upper,
                "valido": True,
                "descricao": desc,
                "regime": "normal",
                "tabela": "CST_PIS_COFINS",
            }
        desc_e = CST_IPI_ENTRADA.get(cst_upper)
        if desc_e:
            return {
                "cst": cst_upper,
                "valido": True,
                "descricao": desc_e,
                "regime": "normal",
                "tabela": "CST_IPI_ENTRADA",
            }
        desc_s = CST_IPI_SAIDA.get(cst_upper)
        if desc_s:
            return {
                "cst": cst_upper,
                "valido": True,
                "descricao": desc_s,
                "regime": "normal",
                "tabela": "CST_IPI_SAIDA",
            }

    return {
        "cst": cst_upper,
        "valido": False,
        "descricao": None,
        "regime": regime_lower,
        "tabela": None,
    }


def buscar_aliquota_icms(uf_origem: str, uf_destino: str) -> dict[str, Any] | None:
    """Retorna as alíquotas ICMS para uma operação interestadual ou intraestadual.

    Para operações interestaduais (UF origem != UF destino), retorna a alíquota
    interestadual (7% ou 12%) e o DIFAL conforme EC 87/2015.

    Para operações intraestaduais (UF origem == UF destino), retorna a alíquota
    interna da UF com alíquota_interestadual == alíquota interna e diferencial == 0.

    Retorna None se alguma UF for inválida.
    """
    uf_o = uf_origem.strip().upper()
    uf_d = uf_destino.strip().upper()

    aliq_interna_d = ICMS_ALIQUOTA_INTERNA.get(uf_d)
    aliq_interna_o = ICMS_ALIQUOTA_INTERNA.get(uf_o)

    if aliq_interna_d is None or aliq_interna_o is None:
        return None

    # Operação intraestadual: usa a alíquota interna da UF, DIFAL = 0
    if uf_o == uf_d:
        return {
            "uf_origem": uf_o,
            "uf_destino": uf_d,
            "aliquota_interestadual": aliq_interna_o,
            "aliquota_interna_destino": aliq_interna_d,
            "diferencial_aliquota": 0.0,
            "fundamento": "Operação intraestadual - aplica-se a alíquota interna da UF",
        }

    aliq_inter = _calcular_aliquota_interestadual(uf_o, uf_d)
    difal = round(aliq_interna_d - aliq_inter, 4)

    fundamento = "Resolução SF 22/2008 (alíquotas interestaduais 7%/12%) + EC 87/2015 (DIFAL)"
    if aliq_inter == 4.0:
        fundamento = "Resolução SF 13/2012 (4% para bens importados) + EC 87/2015 (DIFAL)"

    return {
        "uf_origem": uf_o,
        "uf_destino": uf_d,
        "aliquota_interestadual": aliq_inter,
        "aliquota_interna_destino": aliq_interna_d,
        "diferencial_aliquota": difal,
        "fundamento": fundamento,
    }


def buscar_ncm(codigo: str) -> dict[str, Any] | None:
    """
    Busca um NCM no banco SQLite bundled.

    Retorna None se o banco não existir ou o código não for encontrado.
    """
    conn = _get_conn()
    if conn is None:
        return None
    codigo_limpo = codigo.replace(".", "").replace("-", "").strip()
    row = conn.execute(
        "SELECT codigo, descricao, aliquota_ipi, unidade_tributavel, ex_tipi FROM ncm WHERE codigo = ?",
        (codigo_limpo,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def buscar_cest(codigo: str) -> dict[str, Any] | None:
    """
    Busca um CEST no banco SQLite bundled.

    Retorna None se o banco não existir ou o código não for encontrado.
    """
    conn = _get_conn()
    if conn is None:
        return None
    codigo_limpo = codigo.replace(".", "").strip()
    row = conn.execute(
        "SELECT cest, descricao, segmento FROM cest WHERE cest = ?",
        (codigo_limpo,),
    ).fetchone()
    if row is None:
        return None
    ncm_rows = conn.execute(
        "SELECT ncm FROM cest_ncm WHERE cest = ?",
        (codigo_limpo,),
    ).fetchall()
    ncm_relacionados = [r["ncm"] for r in ncm_rows]
    resultado = dict(row)
    resultado["ncm_relacionados"] = ncm_relacionados
    return resultado
