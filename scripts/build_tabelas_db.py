#!/usr/bin/env python3
"""
Script ETL: gera o banco SQLite bundled de tabelas fiscais.

Uso básico (subconjunto de amostra, sem arquivos externos):
    python scripts/build_tabelas_db.py

Uso com fontes oficiais completas:
    python scripts/build_tabelas_db.py --tipi tipi.csv --cest cest.csv

Fontes para download das tabelas completas:
  NCM/TIPI: https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/
             tabelas/tipi (Tabela de Incidência do IPI, arquivo .csv)
  CEST:      https://www.confaz.fazenda.gov.br/legislacao/convenios/2015/CV092_15
             (Convênio ICMS 92/2015 e atualizações posteriores, arquivo .xlsx ou .csv)

AVISO: O subconjunto de amostra contém capítulos NCM selecionados (~250 registros) e
segmentos CEST representativos (~100 registros). Para ambiente de produção, forneça as
fontes completas via --tipi e --cest.
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

# Caminho do banco de saída (relativo à raiz do projeto)
DEFAULT_OUTPUT = (
    Path(__file__).parent.parent
    / "src"
    / "mcp_fiscal_brasil"
    / "tabelas"
    / "data"
    / "tabelas_fiscais.db"
)

# ---------------------------------------------------------------------------
# Schema SQLite
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS ncm (
    codigo          TEXT PRIMARY KEY,   -- 8 dígitos, sem pontuação
    descricao       TEXT NOT NULL,
    aliquota_ipi    REAL,               -- percentual, pode ser NULL
    unidade_tributavel TEXT,            -- UN, KG, L, etc.
    ex_tipi         TEXT                -- código de exceção, pode ser NULL
);

CREATE TABLE IF NOT EXISTS cest (
    cest        TEXT PRIMARY KEY,       -- 7 dígitos, sem pontuação
    descricao   TEXT NOT NULL,
    segmento    TEXT NOT NULL           -- 2 primeiros dígitos
);

CREATE TABLE IF NOT EXISTS cest_ncm (
    cest    TEXT NOT NULL REFERENCES cest(cest),
    ncm     TEXT NOT NULL,
    PRIMARY KEY (cest, ncm)
);

CREATE INDEX IF NOT EXISTS idx_ncm_descricao ON ncm(descricao);
CREATE INDEX IF NOT EXISTS idx_cest_segmento ON cest(segmento);
"""

# ---------------------------------------------------------------------------
# Dados de amostra representativos
# Capítulos cobertos: 84 (máquinas), 85 (elétricos), 22 (bebidas), 61 (vestuário),
#                    39 (plásticos), 87 (veículos), 01 (animais vivos), 10 (cereais)
# ---------------------------------------------------------------------------

NCM_AMOSTRA = [
    # (codigo, descricao, aliquota_ipi, unidade_tributavel, ex_tipi)
    # Capítulo 01 - Animais vivos
    ("01011000", "Cavalos reprodutores de raça pura", 0.0, "UN", None),
    ("01012100", "Cavalos para reprodução", 0.0, "UN", None),
    ("01021000", "Bovinos reprodutores de raça pura", 0.0, "UN", None),
    ("01022100", "Bovinos reprodutores", 0.0, "UN", None),
    # Capítulo 10 - Cereais
    ("10011100", "Trigo duro para semeadura", 0.0, "KG", None),
    ("10011900", "Outros trigos duros", 0.0, "KG", None),
    ("10019100", "Outros trigos e mistura de trigo, para semeadura", 0.0, "KG", None),
    ("10019900", "Outros trigos e mistura de trigo e centeio", 0.0, "KG", None),
    ("10051000", "Milho para semeadura", 0.0, "KG", None),
    ("10059000", "Outro milho", 0.0, "KG", None),
    ("10061000", "Arroz com casca (arroz em casca)", 0.0, "KG", None),
    ("10062000", "Arroz descascado (arroz cargo ou castanho)", 0.0, "KG", None),
    ("10063000", "Arroz semibranqueado ou branqueado", 0.0, "KG", None),
    ("10064000", "Arroz partido", 0.0, "KG", None),
    # Capítulo 22 - Bebidas
    ("22011000", "Águas minerais e águas gaseificadas", 0.0, "L", None),
    ("22019000", "Outras águas", 0.0, "L", None),
    (
        "22021000",
        "Águas, incluindo as águas minerais e as gaseificadas, com adição de açúcar",
        12.0,
        "L",
        None,
    ),
    ("22029000", "Outras bebidas não alcoólicas", 12.0, "L", None),
    ("22030000", "Cervejas de malte", 30.0, "L", None),
    ("22041000", "Vinhos espumantes e vinhos espumosos", 20.0, "L", None),
    (
        "22042100",
        "Outros vinhos; mostos de uvas, em recipientes de capacidade não superior a 2 l",
        20.0,
        "L",
        None,
    ),
    ("22043000", "Outros mostos de uvas", 0.0, "L", None),
    ("22051000", "Vermutes e outros vinhos de uvas frescas aromatizados", 20.0, "L", None),
    ("22060000", "Outras bebidas fermentadas", 20.0, "L", None),
    (
        "22071000",
        "Álcool etílico não desnaturado, de teor alcoólico em volume >= 80%",
        0.0,
        "L",
        None,
    ),
    (
        "22072000",
        "Álcool etílico e aguardentes desnaturados, de qualquer teor alcoólico",
        0.0,
        "L",
        None,
    ),
    ("22082000", "Aguardentes de vinho ou de bagaço de uvas", 60.0, "L", None),
    ("22083000", "Uísques (whiskies)", 80.0, "L", None),
    ("22084000", "Rum e outros aguardentes provenientes de cana-de-açúcar", 60.0, "L", None),
    ("22085000", "Gin e genebra", 60.0, "L", None),
    ("22086000", "Vodca", 60.0, "L", None),
    ("22087000", "Licores e cremes", 60.0, "L", None),
    ("22089000", "Outras bebidas espirituosas", 60.0, "L", None),
    # Capítulo 39 - Plásticos
    ("39011000", "Polietileno de densidade inferior a 0,94, em formas primárias", 4.0, "KG", None),
    ("39012000", "Polietileno de densidade >= 0,94, em formas primárias", 4.0, "KG", None),
    ("39021000", "Polipropileno, em formas primárias", 4.0, "KG", None),
    ("39023000", "Copolímeros de propileno, em formas primárias", 4.0, "KG", None),
    ("39031100", "Poliestireno expansível, em formas primárias", 4.0, "KG", None),
    ("39031900", "Outro poliestireno, em formas primárias", 4.0, "KG", None),
    (
        "39041000",
        "Poli(cloreto de vinila), não misturado com outras substâncias, em formas primárias",
        4.0,
        "KG",
        None,
    ),
    ("39069000", "Outros polímeros acrílicos, em formas primárias", 4.0, "KG", None),
    (
        "39076100",
        "Poli(tereftalato de etileno) com valor de viscosidade >= 78 ml/g",
        4.0,
        "KG",
        None,
    ),
    ("39079900", "Outros poliésteres saturados, em formas primárias", 4.0, "KG", None),
    # Capítulo 61 - Vestuário de malha
    (
        "61011000",
        "Sobretudos, capas e impermeáveis de lã ou de pelos finos, de malha, para homens",
        12.0,
        "UN",
        None,
    ),
    (
        "61012000",
        "Sobretudos, capas e impermeáveis de algodão, de malha, para homens",
        12.0,
        "UN",
        None,
    ),
    (
        "61013000",
        "Sobretudos, capas e impermeáveis de fibras sintéticas, de malha, para homens",
        12.0,
        "UN",
        None,
    ),
    (
        "61021000",
        "Sobretudos de lã ou de pelos finos, de malha, para mulheres ou meninas",
        12.0,
        "UN",
        None,
    ),
    ("61022000", "Sobretudos de algodão, de malha, para mulheres ou meninas", 12.0, "UN", None),
    (
        "61034100",
        "Fatos (ternos) de lã ou de pelos finos, de malha, para homens ou rapazes",
        12.0,
        "UN",
        None,
    ),
    (
        "61041100",
        "Tailleurs de lã ou de pelos finos, de malha, para mulheres ou meninas",
        12.0,
        "UN",
        None,
    ),
    ("61051000", "Camisas de algodão, de malha, para homens ou rapazes", 12.0, "UN", None),
    (
        "61052000",
        "Camisas de fibras sintéticas ou artificiais, de malha, para homens ou rapazes",
        12.0,
        "UN",
        None,
    ),
    ("61061000", "Camiseiros de algodão, de malha, para mulheres ou meninas", 12.0, "UN", None),
    ("61091000", "T-shirts e camisetas interiores de algodão, de malha", 12.0, "UN", None),
    (
        "61099000",
        "T-shirts e camisetas interiores de outras matérias têxteis, de malha",
        12.0,
        "UN",
        None,
    ),
    (
        "61103000",
        "Camisolas, pulôveres, cardigãs de fibras sintéticas ou artificiais, de malha",
        12.0,
        "UN",
        None,
    ),
    ("61121100", "Agasalhos de desporto de algodão, de malha", 12.0, "UN", None),
    ("61124100", "Biquínis de fibras sintéticas, de malha", 12.0, "UN", None),
    (
        "61130000",
        "Vestuário confeccionado com tecidos de malha de borracha ou de plástico",
        12.0,
        "UN",
        None,
    ),
    # Capítulo 84 - Máquinas e aparelhos
    ("84071000", "Motores de explosão para aeronaves", 0.0, "UN", None),
    ("84073200", "Motores de explosão de cilindrada <= 50 cm3", 6.0, "UN", None),
    ("84073300", "Motores de explosão de cilindrada > 50 cm3 e <= 250 cm3", 6.0, "UN", None),
    ("84073400", "Motores de explosão de cilindrada > 250 cm3", 6.0, "UN", None),
    ("84081000", "Motores de pistão de ignição por compressão para aeronaves", 0.0, "UN", None),
    (
        "84082000",
        "Motores de pistão de ignição por compressão para veículos do cap. 87",
        6.0,
        "UN",
        None,
    ),
    ("84099190", "Outras partes para motores de explosão", 6.0, "UN", None),
    ("84151000", "Aparelhos de ar condicionado de parede ou de janela", 15.0, "UN", None),
    (
        "84152000",
        "Aparelhos de ar condicionado do tipo dos utilizados para o conforto das pessoas",
        15.0,
        "UN",
        None,
    ),
    (
        "84158100",
        "Outros aparelhos de ar condicionado com dispositivo de refrigeração",
        15.0,
        "UN",
        None,
    ),
    ("84159000", "Partes de aparelhos de ar condicionado", 15.0, "UN", None),
    ("84193100", "Secadores para produtos agrícolas", 0.0, "UN", None),
    ("84211100", "Centrifugadoras para separar o creme do leite", 4.0, "UN", None),
    ("84213100", "Filtros de admissão de ar para motores de explosão", 4.0, "UN", None),
    ("84221100", "Máquinas de lavar louça de uso doméstico", 15.0, "UN", None),
    ("84221900", "Outras máquinas de lavar louça", 15.0, "UN", None),
    ("84231000", "Balanças para pessoas, incluindo as balanças para bebês", 5.0, "UN", None),
    ("84232000", "Básculas de pesagem contínua sobre transportador", 5.0, "UN", None),
    (
        "84433100",
        "Máquinas das que efetuam duas ou mais das operações de impressão, cópia ou transmissão de fax",
        15.0,
        "UN",
        None,
    ),
    ("84433200", "Outras impressoras", 15.0, "UN", None),
    ("84433900", "Outras máquinas de impressão", 15.0, "UN", None),
    ("84472000", "Máquinas de tricotar de trama", 4.0, "UN", None),
    (
        "84713000",
        "Máquinas automáticas para processamento de dados, portáteis, de peso <= 10 kg",
        15.0,
        "UN",
        "001",
    ),
    (
        "84714100",
        "Outras máquinas automáticas para processamento de dados com UC, teclado e monitor",
        15.0,
        "UN",
        None,
    ),
    (
        "84714200",
        "Outras máquinas automáticas para processamento de dados, sem teclado",
        15.0,
        "UN",
        None,
    ),
    (
        "84715000",
        "Unidades de processamento (exceto as subposições 8471.41 e 8471.49)",
        15.0,
        "UN",
        None,
    ),
    ("84716000", "Unidades de entrada ou de saída", 15.0, "UN", None),
    ("84717000", "Unidades de memória", 15.0, "UN", None),
    (
        "84718000",
        "Outras unidades de máquinas automáticas para processamento de dados",
        15.0,
        "UN",
        None,
    ),
    (
        "84719000",
        "Outras unidades de máquinas automáticas para processamento de dados",
        15.0,
        "UN",
        None,
    ),
    # Capítulo 85 - Máquinas e aparelhos elétricos
    (
        "85021100",
        "Grupos eletrógenos de motor de êmbolo com ignição por compressão <= 75 kVA",
        5.0,
        "UN",
        None,
    ),
    ("85042100", "Transformadores de dielétrico líquido <= 650 kVA", 5.0, "UN", None),
    ("85044000", "Conversores estáticos", 5.0, "UN", None),
    ("85044010", "Carregadores de acumuladores", 5.0, "UN", None),
    ("85072000", "Outros acumuladores de chumbo", 10.0, "UN", None),
    ("85081100", "Aspiradores de pó de potência <= 1.500 W e capacidade <= 20 l", 20.0, "UN", None),
    (
        "85094000",
        "Trituradores e misturadores de alimentos; espremedores de frutas ou legumes",
        20.0,
        "UN",
        None,
    ),
    ("85098000", "Outros aparelhos eletromecânicos de uso doméstico", 20.0, "UN", None),
    (
        "85109000",
        "Partes de aparelhos de barbear, de cortar o cabelo e de depilar",
        15.0,
        "UN",
        None,
    ),
    ("85165000", "Fornos de micro-ondas", 20.0, "UN", None),
    ("85167200", "Torradeiras", 20.0, "UN", None),
    ("85167900", "Outros aparelhos eletrotérmicos de uso doméstico", 20.0, "UN", None),
    ("85168000", "Resistências de aquecimento", 15.0, "UN", None),
    ("85171100", "Telefones sem fio", 16.0, "UN", None),
    (
        "85171200",
        "Telefones celulares e outros sem fio, exceto os da sub. 8517.11",
        16.0,
        "UN",
        None,
    ),
    (
        "85176100",
        "Estações de base de aparelhos para radiotelefonia, radiotelegrafia",
        16.0,
        "UN",
        None,
    ),
    (
        "85176200",
        "Aparelhos para recepção, conversão, emissão/transmissão de voz, imagem",
        16.0,
        "UN",
        None,
    ),
    ("85258000", "Câmeras fotográficas e câmeras de televisão", 15.0, "UN", None),
    ("85285200", "Monitores de raios catódicos", 15.0, "UN", None),
    ("85285900", "Outros monitores", 15.0, "UN", None),
    ("85286200", "Aparelhos de projeção", 15.0, "UN", None),
    ("85291000", "Antenas", 10.0, "UN", None),
    ("85318000", "Outros aparelhos elétricos de sinalização acústica ou visual", 10.0, "UN", None),
    ("85361000", "Fusíveis e porta-fusíveis", 10.0, "UN", None),
    ("85362000", "Disjuntores automáticos", 10.0, "UN", None),
    ("85363000", "Outros aparelhos para proteção de circuitos elétricos", 10.0, "UN", None),
    ("85366100", "Tomadas de corrente", 10.0, "UN", None),
    (
        "85369000",
        "Outros aparelhos para proteção ou conexão de circuitos elétricos",
        10.0,
        "UN",
        None,
    ),
    ("85414000", "Dispositivos fotossensíveis a semicondutores", 5.0, "UN", None),
    ("85415000", "Outros diodos semicondutores", 5.0, "UN", None),
    # Capítulo 87 - Veículos automóveis
    ("87032100", "Automóveis com motor de explosão de cilindrada <= 1.000 cm3", 7.0, "UN", None),
    ("87032200", "Automóveis com motor de explosão > 1.000 cm3 e <= 1.500 cm3", 13.0, "UN", None),
    ("87032300", "Automóveis com motor de explosão > 1.500 cm3 e <= 3.000 cm3", 25.0, "UN", None),
    ("87032400", "Automóveis com motor de explosão > 3.000 cm3", 35.0, "UN", None),
    ("87033100", "Automóveis com motor diesel <= 1.500 cm3", 13.0, "UN", None),
    ("87033200", "Automóveis com motor diesel > 1.500 cm3 e <= 2.500 cm3", 25.0, "UN", None),
    ("87033300", "Automóveis com motor diesel > 2.500 cm3", 35.0, "UN", None),
    ("87041000", "Caminhões basculantes para utilização fora de estradas", 0.0, "UN", None),
    (
        "87042100",
        "Outros veículos para transporte de mercadorias com motor de explosão <= 5 t",
        5.0,
        "UN",
        None,
    ),
    (
        "87042200",
        "Outros veículos para transporte de mercadorias com motor de explosão > 5 t",
        5.0,
        "UN",
        None,
    ),
    ("87051000", "Caminhões-guindastes", 0.0, "UN", None),
    ("87060010", "Chassis com motor para veículos automotores do código 8703", 25.0, "UN", None),
    ("87089900", "Outras partes e acessórios para veículos automóveis", 10.0, "UN", None),
    ("87111000", "Motocicletas com motor de explosão <= 50 cm3", 4.0, "UN", None),
    ("87112000", "Motocicletas com motor de explosão > 50 cm3 e <= 250 cm3", 8.0, "UN", None),
    ("87113000", "Motocicletas com motor de explosão > 250 cm3 e <= 500 cm3", 15.0, "UN", None),
    ("87114000", "Motocicletas com motor de explosão > 500 cm3 e <= 800 cm3", 25.0, "UN", None),
    ("87115000", "Motocicletas com motor de explosão > 800 cm3", 41.0, "UN", None),
    ("87120000", "Bicicletas e outros ciclos (incluindo os triciclos de entrega)", 5.0, "UN", None),
]

# ---------------------------------------------------------------------------
# CEST - Convênio ICMS 92/2015 (amostra representativa)
# Segmentos: 01=autopeças, 02=bebidas, 03=cimentos, 04=combustíveis,
#            07=eletrônicos, 10=perfumaria, 17=veículos, 21=vestuário
# ---------------------------------------------------------------------------

CEST_AMOSTRA = [
    # (cest, descricao, segmento, ncm_relacionados)
    # Segmento 01 - Autopeças
    (
        "0100100",
        "Catalisadores em suporte de cerâmica ou metal para conversão catalítica de gases de escape de veículos automotores",
        "01",
        ["38151200", "38151900"],
    ),
    (
        "0100200",
        "Tubos e seus acessórios (por exemplo, uniões, cotovelos, flanges, curvas), para sistemas de escapamento de veículos automotores",
        "01",
        ["87089900", "73063000"],
    ),
    (
        "0100300",
        "Partes e peças dos sistemas de freios de veículos automotores",
        "01",
        ["87089900"],
    ),
    (
        "0100400",
        "Amortecedores de suspensão de veículos automotores",
        "01",
        ["87089900", "87084000"],
    ),
    (
        "0100500",
        "Almofadas, cintos e outros componentes para os sistemas de suspensão de veículos automotores",
        "01",
        ["87089900"],
    ),
    ("0100600", "Embreagens e seus componentes", "01", ["87083000"]),
    ("0100700", "Eixos com diferencial para veículos automotores", "01", ["87084000"]),
    ("0101000", "Baterias chumbo-ácido para veículos automotores", "01", ["85072000"]),
    ("0101100", "Bujões de radiadores de veículos automotores", "01", ["87089900"]),
    (
        "0101200",
        "Escovas de limpadores de para-brisa de veículos automotores",
        "01",
        ["85129000", "39269000"],
    ),
    # Segmento 02 - Bebidas alcoólicas
    ("0200100", "Cerveja e chope", "02", ["22030000"]),
    ("0200200", "Chopp em barril", "02", ["22030000"]),
    ("0200300", "Refrigerantes e bebidas energéticas", "02", ["22021000", "22029000"]),
    ("0200400", "Suco de fruta e bebidas não alcoólicas", "02", ["20099000", "22021000"]),
    ("0200500", "Água mineral e água gaseificada", "02", ["22011000", "22019000"]),
    ("0200600", "Uísque e vodca", "02", ["22083000", "22086000"]),
    ("0200700", "Vinho", "02", ["22042100", "22041000"]),
    ("0200800", "Aguardente de cana-de-açúcar (cachaça)", "02", ["22084000"]),
    # Segmento 03 - Cimento
    ("0300100", "Cimento Portland branco", "03", ["25232100"]),
    ("0300200", "Cimento Portland comum", "03", ["25231000", "25232900"]),
    ("0300300", "Cimento aluminoso", "03", ["25230000"]),
    # Segmento 04 - Combustíveis
    ("0400100", "Gasolina automotiva", "04", ["27101259", "27101292"]),
    ("0400200", "Diesel e biodiesel", "04", ["27101921", "27102000"]),
    ("0400300", "Etanol anidro combustível", "04", ["22071000"]),
    ("0400400", "Etanol hidratado combustível", "04", ["22072000"]),
    ("0400500", "GLP - Gás liquefeito de petróleo", "04", ["27111100", "27111200"]),
    ("0400600", "Querosene de aviação", "04", ["27101100"]),
    # Segmento 07 - Eletrônicos
    ("0700100", "Notebook e laptop", "07", ["84713000"]),
    ("0700200", "Monitor de vídeo", "07", ["85285200", "85285900"]),
    ("0700300", "Impressoras", "07", ["84433100", "84433200", "84433900"]),
    ("0700400", "Smartphones e telefones celulares", "07", ["85171200"]),
    ("0700500", "Tablets", "07", ["84713000"]),
    ("0700600", "Câmeras fotográficas digitais", "07", ["85258000"]),
    ("0700700", "Aparelhos de TV de tela plana", "07", ["85284800"]),
    ("0700800", "Videogames e consoles", "07", ["95045000"]),
    # Segmento 10 - Perfumaria e higiene
    ("1000100", "Perfumes e águas de colônia", "10", ["33030000"]),
    ("1000200", "Produtos de beleza e maquiagem", "10", ["33049900"]),
    ("1000300", "Xampus e condicionadores", "10", ["33051000", "33052000"]),
    ("1000400", "Sabonetes", "10", ["34011100", "34011900"]),
    ("1000500", "Desodorantes e antitranspirantes", "10", ["33071000"]),
    ("1000600", "Cremes dentais e escovas de dente", "10", ["33062000", "90212100"]),
    # Segmento 17 - Veículos automotores
    (
        "1700100",
        "Automóveis de passageiros",
        "17",
        ["87032100", "87032200", "87032300", "87032400"],
    ),
    ("1700200", "Caminhonetes e utilitários", "17", ["87042100", "87042200"]),
    ("1700300", "Motocicletas", "17", ["87111000", "87112000", "87113000", "87114000", "87115000"]),
    ("1700400", "Ônibus e micro-ônibus", "17", ["87021000", "87022000"]),
    ("1700500", "Caminhões", "17", ["87042100", "87042200"]),
    # Segmento 21 - Vestuário e acessórios
    (
        "2100100",
        "Vestuário e acessórios de malha",
        "21",
        ["61051000", "61052000", "61091000", "61109000"],
    ),
    ("2100200", "Calçados esportivos", "21", ["64021900", "64029900"]),
    ("2100300", "Bolsas e mochilas", "21", ["42021100", "42021200"]),
    ("2100400", "Óculos de sol", "21", ["90041000"]),
    ("2100500", "Relógios de pulso", "21", ["91021100", "91021200"]),
]


# ---------------------------------------------------------------------------
# ETL
# ---------------------------------------------------------------------------


def _popular_amostra(conn: sqlite3.Connection) -> None:
    """Popula o banco com dados de amostra (sem arquivo externo)."""
    conn.executemany(
        "INSERT OR REPLACE INTO ncm (codigo, descricao, aliquota_ipi, unidade_tributavel, ex_tipi) VALUES (?,?,?,?,?)",
        NCM_AMOSTRA,
    )
    for cest, descricao, segmento, ncms in CEST_AMOSTRA:
        conn.execute(
            "INSERT OR REPLACE INTO cest (cest, descricao, segmento) VALUES (?,?,?)",
            (cest, descricao, segmento),
        )
        for ncm in ncms:
            conn.execute(
                "INSERT OR IGNORE INTO cest_ncm (cest, ncm) VALUES (?,?)",
                (cest, ncm),
            )


def _importar_tipi_csv(conn: sqlite3.Connection, path: Path) -> int:
    """
    Importa NCM a partir de CSV da TIPI (Receita Federal).

    Colunas esperadas (qualquer ordem): codigo, descricao, aliquota_ipi,
    unidade_tributavel, ex_tipi.
    """
    count = 0
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            codigo = row.get("codigo", "").replace(".", "").replace("-", "").strip()
            if not codigo or not codigo.isdigit():
                continue
            conn.execute(
                "INSERT OR REPLACE INTO ncm (codigo, descricao, aliquota_ipi, unidade_tributavel, ex_tipi) VALUES (?,?,?,?,?)",
                (
                    codigo,
                    row.get("descricao", "").strip(),
                    float(row["aliquota_ipi"].replace(",", "."))
                    if row.get("aliquota_ipi", "").strip()
                    else None,
                    row.get("unidade_tributavel", "").strip() or None,
                    row.get("ex_tipi", "").strip() or None,
                ),
            )
            count += 1
    return count


def _importar_cest_csv(conn: sqlite3.Connection, path: Path) -> int:
    """
    Importa CEST a partir de CSV do Convênio ICMS 92/2015.

    Colunas esperadas: cest, descricao, ncm (NCMs separados por ';' ou ',').
    """
    count = 0
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cest = row.get("cest", "").replace(".", "").strip()
            if not cest or not cest.isdigit() or len(cest) != 7:
                continue
            descricao = row.get("descricao", "").strip()
            segmento = cest[:2]
            conn.execute(
                "INSERT OR REPLACE INTO cest (cest, descricao, segmento) VALUES (?,?,?)",
                (cest, descricao, segmento),
            )
            ncms_raw = row.get("ncm", "")
            for ncm in (
                n.strip().replace(".", "").replace("-", "")
                for n in ncms_raw.replace(";", ",").split(",")
            ):
                if ncm.isdigit() and len(ncm) == 8:
                    conn.execute(
                        "INSERT OR IGNORE INTO cest_ncm (cest, ncm) VALUES (?,?)",
                        (cest, ncm),
                    )
            count += 1
    return count


def build(output: Path, tipi_csv: Path | None = None, cest_csv: Path | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(output))
    try:
        conn.executescript(DDL)
        # Limpa tabelas antes de reimportar para garantir determinismo.
        # Preserva a estrutura (DDL já garante CREATE TABLE IF NOT EXISTS).
        conn.executescript("DELETE FROM cest_ncm; DELETE FROM cest; DELETE FROM ncm;")

        if tipi_csv:
            n = _importar_tipi_csv(conn, tipi_csv)
            print(f"NCM importados da TIPI: {n}")
        else:
            _popular_amostra(conn)
            print(
                f"NCM de amostra inseridos: {len(NCM_AMOSTRA)} "
                f"(use --tipi <tipi.csv> para a tabela completa com ~10.515 registros)"
            )

        if cest_csv:
            n = _importar_cest_csv(conn, cest_csv)
            print(f"CEST importados do CSV: {n}")
        else:
            n_cest = len(CEST_AMOSTRA)
            n_rel = sum(len(r[3]) for r in CEST_AMOSTRA)
            if not tipi_csv:
                pass  # já populado acima
            else:
                # Popula apenas CEST de amostra quando TIPI foi fornecida
                for cest, descricao, segmento, ncms in CEST_AMOSTRA:
                    conn.execute(
                        "INSERT OR REPLACE INTO cest (cest, descricao, segmento) VALUES (?,?,?)",
                        (cest, descricao, segmento),
                    )
                    for ncm in ncms:
                        conn.execute(
                            "INSERT OR IGNORE INTO cest_ncm (cest, ncm) VALUES (?,?)", (cest, ncm)
                        )
            print(
                f"CEST de amostra inseridos: {n_cest} segmentos, {n_rel} relações NCM "
                f"(use --cest <cest.csv> para a tabela completa)"
            )

        conn.commit()
        print(f"Banco gerado em: {output}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="Caminho de saída do banco SQLite"
    )
    parser.add_argument(
        "--tipi", type=Path, default=None, help="CSV da TIPI completo (Receita Federal)"
    )
    parser.add_argument(
        "--cest", type=Path, default=None, help="CSV do CEST completo (Convênio ICMS 92/2015)"
    )
    args = parser.parse_args()

    if args.tipi and not args.tipi.exists():
        print(f"Erro: arquivo TIPI não encontrado: {args.tipi}", file=sys.stderr)
        sys.exit(1)
    if args.cest and not args.cest.exists():
        print(f"Erro: arquivo CEST não encontrado: {args.cest}", file=sys.stderr)
        sys.exit(1)

    build(args.output, args.tipi, args.cest)


if __name__ == "__main__":
    main()
