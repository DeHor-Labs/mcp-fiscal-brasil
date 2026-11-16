import unicodedata
from typing import Any

from mcp_fiscal_brasil._core import FiscalError, FiscalHTTPError, get_logger, settings

from ..shared import cpfcnpj as cpfcnpj_provider
from .schemas import (
    SITUACAO_REGULAR,
    SITUACOES_CPF,
    ComprovanteCPF,
    CPFCadastro,
    CPFValidation,
    EnderecoCPF,
    SituacaoCPF,
)

logger = get_logger(__name__)

# Codigo de erro do provedor para CPF valido mas ausente nas bases da Receita.
ERRO_CPF_INEXISTENTE = 102

# Texto que, sem codigo, indica situacao regular (apta a emissao).
_SITUACAO_REGULAR_TEXTO = "regular"


def _normalizar_situacao(texto: str) -> str:
    """Normaliza o rotulo da situacao para comparacao: casefold sem acentos."""
    decomposto = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in decomposto if not unicodedata.combining(c)).strip()


# Rotulos conhecidos de situacao NAO regular (derivados da tabela oficial mais os
# sinonimos genericos que o provedor pode devolver sem o codigo). Sao a evidencia
# que autoriza apto_emissao=False; texto fora dessa lista fica indeterminado (None),
# para nunca produzir True sem evidencia de regularidade.
_SITUACOES_NAO_REGULARES = frozenset(
    _normalizar_situacao(rotulo)
    for codigo, rotulo in SITUACOES_CPF.items()
    if codigo != SITUACAO_REGULAR
) | {"cancelada", "cancelado", "cancelada de oficio", "falecido"}

_SEM_TOKEN_CPF = (
    "consultar_cpf exige o provedor premium opcional cpfcnpj.com.br: configure "
    "CPFCNPJ_TOKEN. Nao ha fonte gratuita de situacao cadastral de CPF (a Receita "
    "Federal nao publica API aberta de dados de pessoa fisica)."
)


def unformat_cpf(cpf: str) -> str:
    """Remove a formatação do CPF, retornando apenas números."""
    return "".join(c for c in cpf if c.isdigit())


def format_cpf(cpf: str) -> str:
    """Formata uma string de números como CPF (XXX.XXX.XXX-XX)."""
    clean = unformat_cpf(cpf)
    if len(clean) != 11:
        return cpf  # Retorna original se não tem 11 dígitos
    return f"{clean[:3]}.{clean[3:6]}.{clean[6:9]}-{clean[9:]}"


def _calcular_digito_cpf(cpf_parcial: str) -> str:
    """Calcula um dígito verificador do CPF."""
    soma = 0
    peso = len(cpf_parcial) + 1
    for digito in cpf_parcial:
        soma += int(digito) * peso
        peso -= 1

    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def validate_cpf(cpf: str) -> CPFValidation:
    """Valida um CPF usando o algoritmo dos dígitos verificadores."""
    clean_cpf = unformat_cpf(cpf)

    # Formato básico
    if len(clean_cpf) != 11 or len(set(clean_cpf)) == 1:
        return CPFValidation(cpf_formatado=cpf, válido=False, digitos_verificadores_ok=False)

    cpf_9 = clean_cpf[:9]
    dv1 = _calcular_digito_cpf(cpf_9)
    dv2 = _calcular_digito_cpf(cpf_9 + dv1)

    digitos_ok = clean_cpf[9:] == (dv1 + dv2)

    return CPFValidation(
        cpf_formatado=format_cpf(clean_cpf), válido=digitos_ok, digitos_verificadores_ok=digitos_ok
    )


def mascarar_cpf(cpf: str) -> str:
    """Mascara um CPF para uso em log e resposta (``***.***.***-XX``).

    Preserva apenas os dois digitos verificadores (que sao derivaveis dos nove
    primeiros), evitando expor o numero completo do titular.
    """
    digitos = unformat_cpf(cpf)
    if len(digitos) != 11:
        return "***.***.***-**"
    return f"***.***.***-{digitos[9:]}"


def _texto(valor: Any) -> str | None:
    """Normaliza um valor textual do provedor: None quando vazio."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _inteiro(valor: Any) -> int | None:
    """Converte um valor em inteiro quando possivel; None caso contrario."""
    if valor is None or valor == "":
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _codigo_situacao(valor: Any) -> str | None:
    """Normaliza o codigo de situacao para dois digitos (ex.: 3 -> "03")."""
    texto = _texto(valor)
    if texto is None:
        return None
    return texto.zfill(2) if texto.isdigit() else texto


class CPFClient:
    """Cliente de consulta cadastral de CPF pelo provedor premium opcional.

    Diferente do CNPJ, nao existe fonte gratuita de situacao cadastral de CPF:
    a consulta so acontece com CPFCNPJ_TOKEN configurado. A validacao do digito
    verificador ocorre antes, na camada de tools/API/SDK, para nao gastar credito
    com CPF malformado.
    """

    async def consultar(self, cpf: str) -> CPFCadastro:
        """Consulta a situacao cadastral de um CPF no provedor premium.

        Args:
            cpf: CPF com ou sem mascara. Deve ter o digito verificador ja validado.

        Returns:
            CPFCadastro com os campos do pacote configurado (CPFCNPJ_CPF_PACKET).

        Raises:
            FiscalError: Quando o provedor nao esta configurado (sem token) ou
                quando o CPF e valido mas nao consta na base da Receita (erro 102).
            FiscalHTTPError: Demais erros do provedor, repassados sem traducao.
        """
        cpf_digitos = unformat_cpf(cpf)
        if not cpfcnpj_provider.provedor_configurado():
            raise FiscalError(_SEM_TOKEN_CPF)

        pacote = settings.cpfcnpj_cpf_packet
        # Nunca logar o CPF completo nem qualquer PII do titular.
        logger.info("cpf_lookup_started", cpf=mascarar_cpf(cpf_digitos), pacote=pacote)
        try:
            data = await cpfcnpj_provider.consultar(pacote, cpf_digitos)
        except FiscalHTTPError as exc:
            if exc.status_code == ERRO_CPF_INEXISTENTE:
                raise FiscalError(
                    "O CPF informado e valido, mas nao consta na base da Receita "
                    "Federal (nao existe)."
                ) from exc
            raise

        return self._parse_cpfcnpj(data, cpf_digitos)

    def _parse_cpfcnpj(self, data: dict[str, Any], cpf: str) -> CPFCadastro:
        """Transforma a resposta de um pacote de CPF da cpfcnpj.com.br em CPFCadastro."""
        situacao = self._parse_situacao(data)
        apto_emissao = self._derivar_apto_emissao(situacao)

        return CPFCadastro(
            cpf=mascarar_cpf(cpf),
            nome=_texto(data.get("nome")),
            nome_social=_texto(data.get("nomeSocial")),
            nascimento=_texto(data.get("nascimento")),
            genero=_texto(data.get("genero")),
            situacao=situacao,
            endereco=self._parse_endereco(data),
            comprovante=self._parse_comprovante(data),
            apto_emissao=apto_emissao,
            origem="cpfcnpj.com.br",
        )

    @staticmethod
    def _parse_situacao(data: dict[str, Any]) -> SituacaoCPF | None:
        codigo = _codigo_situacao(data.get("situacaoDigito"))
        rotulo = _texto(data.get("situacao"))
        motivo = _texto(data.get("situacaoMotivo"))
        if codigo is None and rotulo is None and motivo is None:
            return None
        descricao = (SITUACOES_CPF.get(codigo) if codigo else None) or rotulo
        return SituacaoCPF(
            codigo=codigo,
            descricao=descricao,
            motivo=motivo,
            data=_texto(data.get("situacaoComprovanteEmissao")),
            ano_obito=_inteiro(data.get("situacaoAnoObito")),
            inscricao=_texto(data.get("situacaoInscricao")),
        )

    @staticmethod
    def _derivar_apto_emissao(situacao: SituacaoCPF | None) -> bool | None:
        """Deriva se o CPF esta apto a emissao a partir da situacao cadastral.

        Prioriza o codigo (``00`` -> apto). Quando o provedor devolve apenas o
        rotulo textual (sem ``situacaoDigito``), deriva do texto normalizado:
        "regular" -> True; rotulos conhecidos de irregularidade -> False; texto
        vazio ou desconhecido -> None. Nunca retorna True sem evidencia.
        """
        if situacao is None:
            return None
        if situacao.codigo is not None:
            return situacao.codigo == SITUACAO_REGULAR
        if not situacao.descricao:
            return None
        normalizado = _normalizar_situacao(situacao.descricao)
        if normalizado == _SITUACAO_REGULAR_TEXTO:
            return True
        if normalizado in _SITUACOES_NAO_REGULARES:
            return False
        return None

    @staticmethod
    def _parse_endereco(data: dict[str, Any]) -> EnderecoCPF | None:
        campos = ("endereco", "numero", "complemento", "bairro", "cep", "cidade", "uf", "ibge")
        if not any(_texto(data.get(campo)) for campo in campos):
            return None
        return EnderecoCPF(
            logradouro=_texto(data.get("endereco")),
            numero=_texto(data.get("numero")),
            complemento=_texto(data.get("complemento")),
            bairro=_texto(data.get("bairro")),
            cep=_texto(data.get("cep")),
            cidade=_texto(data.get("cidade")),
            uf=_texto(data.get("uf")),
            ibge=_texto(data.get("ibge")),
        )

    @staticmethod
    def _parse_comprovante(data: dict[str, Any]) -> ComprovanteCPF | None:
        numero = _texto(data.get("situacaoComprovante"))
        pdf = _texto(data.get("situacaoComprovantePdf"))
        if numero is None and pdf is None:
            return None
        return ComprovanteCPF(numero=numero, pdf_base64=pdf)
