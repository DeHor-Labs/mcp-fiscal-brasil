"""Ferramentas MCP para analise de arquivos SPED."""

from datetime import date

from .._core import get_logger
from .schemas import InfoAberturaSPED, ResumoPeriodoSPED, SPEDAnaliseResponse

logger = get_logger(__name__)

# Identificação do tipo de SPED pelo registro 0000 campo tipo_escrituracao
TIPOS_SPED: dict[str, str] = {
    "0": "EFD-ICMS-IPI",
    "1": "EFD-Contribuicoes",
    "2": "ECD",
    "3": "ECF",
}

# Posições dos campos com valores monetários por registro (layout pipe-delimitado).
# Os índices referem-se à lista campos[1:] retornada por listar_registros_sped
# (ou seja, após remover o campo REG que ocupa a posição 0 da linha completa).
#
# Fontes:
#   EFD-Contribuicoes: Guia Prático EFD Contribuições, Ato COTEPE/ICMS 65/2013
#     M210 campo 7 (índice 6) = VL_CONT_PER (contribuicao PIS apurada no período)
#     M610 campo 7 (índice 6) = VL_CONT_PER (contribuicao COFINS apurada no período)
#     0110 campo 1 (índice 0) = COD_INC_TRIB (1=cumulativo, 2=nao-cumulativo)
#   EFD ICMS/IPI: Guia Prático EFD ICMS/IPI, Ato COTEPE/ICMS 44/2018 (versao 018)
#     E110 layout completo (campos 01 a 15):
#       campo 02 (índice  0) = VL_TOT_DEBITOS       - total de débitos BRUTOS de saídas/prestações
#       campo 03 (índice  1) = VL_AJ_DEBITOS        - ajustes a débito por doc. fiscal
#       campo 04 (índice  2) = VL_TOT_AJ_DEBITOS    - total de ajustes a débito
#       campo 05 (índice  3) = VL_ESTORNOS_CRED     - estornos de créditos
#       campo 06 (índice  4) = VL_TOT_CREDITOS      - total de créditos por entradas
#       campo 07 (índice  5) = VL_AJ_CREDITOS       - ajustes a crédito por doc. fiscal
#       campo 08 (índice  6) = VL_TOT_AJ_CREDITOS   - total de ajustes a crédito
#       campo 09 (índice  7) = VL_ESTORNOS_DEB      - estornos de débitos
#       campo 10 (índice  8) = VL_SLD_CREDOR_ANT    - saldo credor do período anterior
#       campo 11 (índice  9) = VL_SLD_APURADO       - saldo devedor apurado (= débitos - créditos)
#       campo 12 (índice 10) = VL_TOT_DED           - total de deduções
#       campo 13 (índice 11) = VL_ICMS_RECOLHER     - ICMS a recolher (= VL_SLD_APURADO - VL_TOT_DED)
#       campo 14 (índice 12) = VL_SLD_CREDOR_TRANSPORTAR
#       campo 15 (índice 13) = DEB_ESP              - valores extra-apuração
# Constantes de layout expostas como nomes públicos para que módulos consumidores
# (ex.: agentic/sped.py) possam importá-las sem acoplamento a nomes privados (_).
# O typechecker verifica esses imports normalmente pois os nomes são públicos.

CAMPO_VALOR: dict[str, int] = {
    "M210": 6,  # VL_CONT_PER - PIS (campo 7 do registro, índice 6 em campos[1:])
    "M610": 6,  # VL_CONT_PER - COFINS (campo 7 do registro, índice 6 em campos[1:])
}

# Para o registro E110 são extraídos dois campos com semânticas distintas.
# Usar CAMPO_E110_* em vez de CAMPO_VALOR para o processamento especializado do ICMS.
CAMPO_E110_TOT_DEBITOS: int = 0  # campo 02 - VL_TOT_DEBITOS: débitos BRUTOS (informativo)
CAMPO_E110_RECOLHER: int = 11  # campo 13 - VL_ICMS_RECOLHER: valor LÍQUIDO a recolher

# Campo do regime PIS/COFINS no registro 0110
CAMPO_0110_REGIME: int = 0  # COD_INC_TRIB: "1"=cumulativo, "2"=nao-cumulativo
REGIME_0110: dict[str, str] = {
    "1": "cumulativo",
    "2": "nao-cumulativo",
}

# Aliases com underscore mantidos para compatibilidade com código legado.
# Novos módulos devem importar os nomes sem underscore acima.
_CAMPO_VALOR = CAMPO_VALOR
_CAMPO_E110_TOT_DEBITOS = CAMPO_E110_TOT_DEBITOS
_CAMPO_E110_RECOLHER = CAMPO_E110_RECOLHER
_CAMPO_0110_REGIME = CAMPO_0110_REGIME
_REGIME_0110 = REGIME_0110


def _to_float(valor: str | None) -> float:
    """Converte valor monetário SPED (vírgula decimal) para float.

    O layout oficial do SPED (EFD-Contribuições, EFD ICMS/IPI, ECD, ECF)
    define a VÍRGULA como único separador decimal. O ponto, quando presente,
    é separador de milhar (formato brasileiro), conforme Guia Prático EFD
    Contribuições (Ato COTEPE/ICMS 65/2013) e EFD ICMS/IPI (Ato COTEPE/ICMS
    44/2018). Valores no padrão en-US (ponto decimal sem vírgula) não são
    esperados no SPED e, se ocorrerem, serão interpretados como inteiro
    (ponto removido como milhar), o que é seguro para os casos reais.

    Premissa: vírgula é SEMPRE o separador decimal neste contexto.
    Estratégia: remover todos os pontos (milhar) e trocar a vírgula por ponto.

    Exemplos de entradas suportadas:
      "3.708.500,27" -> 3708500.27  (milhar + decimal)
      "1.500,00"     -> 1500.0      (milhar + decimal)
      "3708500,27"   -> 3708500.27  (sem milhar, apenas decimal)
      "100,00"       -> 100.0
      "-500,50"      -> -500.5      (negativo)
      "0"            -> 0.0
      ""             -> 0.0
      None           -> 0.0

    Args:
        valor: String monetária SPED ou None/vazia.

    Returns:
        Valor como float. Retorna 0.0 para entradas vazias, None ou inválidas.
    """
    if not valor or not valor.strip():
        return 0.0
    try:
        # Remove pontos de milhar e converte vírgula decimal para ponto
        normalizado = valor.strip().replace(".", "").replace(",", ".")
        return float(normalizado)
    except ValueError:
        return 0.0


def _parse_linha_sped(linha: str) -> list[str]:
    """Analisa uma linha SPED (delimitada por '|') e remove os pipes externos."""
    if linha.startswith("|"):
        linha = linha[1:]
    if linha.endswith("|"):
        linha = linha[:-1]
    return linha.split("|")


def _to_date(valor: str) -> date | None:
    """Converte data SPED (DDMMAAAA) em objeto date."""
    valor = valor.strip()
    if len(valor) == 8 and valor.isdigit():
        try:
            return date(int(valor[4:]), int(valor[2:4]), int(valor[:2]))
        except ValueError:
            return None
    return None


def _parse_abertura(campos: list[str]) -> InfoAberturaSPED:
    """Analisa o registro 0000 (abertura) do arquivo SPED."""

    # Leiaute EFD ICMS/IPI e EFD Contribuições:
    # |REG|COD_VER|TIP_ESCRIT|IND_SIT|NUM_REC_SCP|NOME|CNPJ|CPF|UF|IE|COD_MUN|SUFRAMA|IND_PERFIL|IND_ATIV|
    def get(i: int) -> str | None:
        return campos[i].strip() if i < len(campos) and campos[i].strip() else None

    return InfoAberturaSPED(
        codigo_versao_leiaute=get(1),
        tipo_escrituracao=get(2),
        indicador_situacao=get(3),
        num_rec_scp=get(4),
        nome_empresarial=get(5),
        cnpj=get(6),
        cpf=get(7),
        uf=get(8),
        ie=get(9),
        cod_municipio=get(10),
        suframa=get(11),
        ind_perfil=get(12),
        ind_ativ=get(13),
    )


async def analisar_sped(conteudo: str, nome_arquivo: str | None = None) -> SPEDAnaliseResponse:
    """
    Analisa um arquivo SPED e extrai informações sobre o período, empresa e tipos de registros.

    Suporta EFD-ICMS/IPI, EFD-Contribuições, ECD e ECF.

    Args:
        conteudo: Conteúdo do arquivo SPED como string (formato pipe-delimitado)
        nome_arquivo: Nome do arquivo (opcional, para informação)

    Returns:
        SPEDAnaliseResponse com resumo do arquivo, informações da empresa e contagem de registros.
    """
    logger.info("sped_analysis_started", nome_arquivo=nome_arquivo or "desconhecido")

    abertura: InfoAberturaSPED | None = None
    tipos_registros: dict[str, int] = {}
    erros: list[str] = []
    avisos: list[str] = []
    periodo_inicial: date | None = None
    periodo_final: date | None = None

    linhas = [linha for linha in conteudo.strip().splitlines() if linha.strip()]
    total = len(linhas)

    for _num_linha, linha in enumerate(linhas, 1):
        linha = linha.strip()
        campos = _parse_linha_sped(linha)
        if not campos:
            continue

        registro = campos[0]
        tipos_registros[registro] = tipos_registros.get(registro, 0) + 1

        # Registro de abertura
        if registro == "0000" and abertura is None:
            abertura = _parse_abertura(campos)
            # Período fica no próximo campo após ind_ativ (índice 14 e 15)
            if len(campos) > 15:
                periodo_inicial = _to_date(campos[14])
                periodo_final = _to_date(campos[15])

    tipo_sped = "Desconhecido"
    if abertura and abertura.tipo_escrituracao:
        tipo_sped = TIPOS_SPED.get(abertura.tipo_escrituracao, f"Tipo {abertura.tipo_escrituracao}")

    # Verifica presença de registros obrigatórios
    if "0000" not in tipos_registros:
        erros.append("Registro 0000 (abertura) não encontrado - arquivo possivelmente inválido")
    if "9999" not in tipos_registros:
        avisos.append("Registro 9999 (encerramento) não encontrado - arquivo pode estar incompleto")

    resumo = ResumoPeriodoSPED(
        periodo_inicial=periodo_inicial,
        periodo_final=periodo_final,
        total_registros=total,
        tipos_registros=tipos_registros,
        cnpj=abertura.cnpj if abertura else None,
        razao_social=abertura.nome_empresarial if abertura else None,
        uf=abertura.uf if abertura else None,
    )

    return SPEDAnaliseResponse(
        tipo_sped=tipo_sped,
        abertura=abertura,
        resumo=resumo,
        avisos=avisos,
        erros=erros,
    )


async def listar_registros_sped(
    conteudo: str, tipo_registro: str
) -> list[dict[str, str | list[str]]]:
    """
    Lista todos os registros de um determinado tipo em um arquivo SPED.

    Args:
        conteudo: Conteúdo do arquivo SPED
        tipo_registro: Código do registro a buscar (ex: 'C100', 'E110', '0140')

    Returns:
        Lista de dicionários com os campos de cada ocorrência do registro.
        Cada dicionário contém:
          - "registro": código do registro (string)
          - "campos": lista de campos (excluindo REG), indexável por posição
          - "raw": linha original intacta (string)
    """
    tipo_registro = tipo_registro.upper().strip()
    resultado: list[dict[str, str | list[str]]] = []

    for linha in conteudo.strip().splitlines():
        linha = linha.strip()
        if not linha:
            continue
        campos = _parse_linha_sped(linha)
        if campos and campos[0] == tipo_registro:
            resultado.append(
                {
                    "registro": tipo_registro,
                    "campos": campos[1:],  # lista indexável, sem o campo REG
                    "raw": linha,
                }
            )

    return resultado
