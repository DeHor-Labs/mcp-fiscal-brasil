"""Schemas para dados de NFe."""

from datetime import datetime

from pydantic import BaseModel, Field

from ..shared.schemas import BaseResponse, Endereco


class EnderecoNFe(Endereco):
    """Endereco especifico do modelo NFe (com CNPJ/CPF)."""

    cnpj: str | None = None
    cpf: str | None = None
    ie: str | None = None
    nome: str | None = None


class ItemNFe(BaseModel):
    """Item (produto ou serviço) de uma NFe."""

    número: int
    codigo_produto: str
    descrição: str
    ncm: str | None = None
    cfop: str
    unidade: str
    quantidade: float
    valor_unitario: float
    valor_total: float
    cst_icms: str | None = None
    aliquota_icms: float | None = None
    valor_icms: float | None = None
    aliquota_ipi: float | None = None
    valor_ipi: float | None = None
    aliquota_pis: float | None = None
    valor_pis: float | None = None
    aliquota_cofins: float | None = None
    valor_cofins: float | None = None
    # Campos Reforma Tributária (NT 2025.002) - opcionais para retrocompatibilidade
    aliquota_ibs_uf: float | None = None
    valor_ibs_uf: float | None = None
    aliquota_ibs_mun: float | None = None
    valor_ibs_mun: float | None = None
    aliquota_cbs: float | None = None
    valor_cbs: float | None = None
    aliquota_is: float | None = None
    valor_is: float | None = None


class TotaisNFe(BaseModel):
    """Totais da NFe."""

    valor_produtos: float | None = None
    valor_desconto: float | None = None
    valor_frete: float | None = None
    valor_seguro: float | None = None
    valor_outras_despesas: float | None = None
    base_calculo_icms: float | None = None
    valor_icms: float | None = None
    valor_icms_desonerado: float | None = None
    base_calculo_icms_st: float | None = None
    valor_icms_st: float | None = None
    valor_ipi: float | None = None
    valor_pis: float | None = None
    valor_cofins: float | None = None
    valor_nota: float | None = None


class TotaisReformaNFe(BaseModel):
    """Totais dos tributos da Reforma Tributária na NF-e (NT 2025.002 - Grupo W03/IBSCBSTot)."""

    base_calculo_ibscbs: float | None = None
    valor_ibs_uf: float | None = None
    valor_ibs_mun: float | None = None
    valor_ibs: float | None = None
    valor_cbs: float | None = None
    valor_is: float | None = None


class NFeResponse(BaseResponse):
    """Dados de uma NFe consultada."""

    chave_acesso: str
    número: str | None = None
    serie: str | None = None
    modelo: str = "55"
    emitente: EnderecoNFe | None = None
    destinatario: EnderecoNFe | None = None
    data_emissao: datetime | None = None
    data_saida_entrada: datetime | None = None
    natureza_operacao: str | None = None
    tipo_operacao: str | None = None  # "0" saida, "1" entrada
    finalidade: str | None = None
    itens: list[ItemNFe] = Field(default_factory=list)
    totais: TotaisNFe | None = None
    totais_reforma: TotaisReformaNFe | None = None
    protocolo_autorizacao: str | None = None
    data_autorizacao: datetime | None = None
    situacao: str | None = None
    informacoes_adicionais: str | None = None


class StatusSEFAZResponse(BaseResponse):
    """Status do serviço SEFAZ de uma UF."""

    uf: str
    status: str
    descrição: str
    código: int | None = None
    ambiente: str = "producao"
    versão: str | None = None
