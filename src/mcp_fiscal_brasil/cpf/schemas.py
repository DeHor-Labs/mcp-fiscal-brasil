from pydantic import BaseModel

# Codigos de situacao cadastral do CPF na Receita Federal. A API devolve o codigo
# em ``situacaoDigito`` (ex.: "03") e, por vezes, um rotulo generico em ``situacao``
# (ex.: "Cancelada"); esta tabela dá a descrição oficial por codigo, preferida no
# mapeamento. Para a regra fiscal, apenas 00 (Regular) libera a emissao de documentos.
SITUACOES_CPF: dict[str, str] = {
    "00": "Regular",
    "02": "Suspensa",
    "03": "Titular Falecido",
    "04": "Pendente de Regularização",
    "05": "Cancelada por Multiplicidade",
    "08": "Nula",
    "09": "Cancelada de Ofício",
}

# Unica situacao que permite emitir documento fiscal para a pessoa fisica.
SITUACAO_REGULAR = "00"


class CPFValidation(BaseModel):
    cpf_formatado: str
    válido: bool
    digitos_verificadores_ok: bool


class SituacaoCPF(BaseModel):
    """Situacao cadastral do CPF na Receita Federal."""

    codigo: str | None = None
    descricao: str | None = None
    motivo: str | None = None
    data: str | None = None
    ano_obito: int | None = None
    inscricao: str | None = None


class EnderecoCPF(BaseModel):
    """Endereco do titular (retornado apenas no pacote 3)."""

    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cep: str | None = None
    cidade: str | None = None
    uf: str | None = None
    ibge: str | None = None


class ComprovanteCPF(BaseModel):
    """Comprovante de situacao cadastral emitido pela Receita (apenas no pacote 8)."""

    numero: str | None = None
    pdf_base64: str | None = None


class CPFCadastro(BaseModel):
    """Cadastro do CPF consultado no provedor premium opcional cpfcnpj.com.br.

    O CPF vem mascarado (``***.***.***-XX``, so os digitos verificadores). Campos
    ausentes no pacote escolhido ficam ``None``. Campos operacionais do provedor
    (saldo, consultaID, pacoteUsado) nao sao expostos.
    """

    cpf: str
    nome: str | None = None
    nome_social: str | None = None
    nascimento: str | None = None
    genero: str | None = None
    situacao: SituacaoCPF | None = None
    endereco: EnderecoCPF | None = None
    comprovante: ComprovanteCPF | None = None
    # Derivado: True apenas com situacao Regular (00); False para as demais
    # situacoes conhecidas; None quando o pacote escolhido nao traz situacao.
    apto_emissao: bool | None = None
    origem: str = "cpfcnpj.com.br"
