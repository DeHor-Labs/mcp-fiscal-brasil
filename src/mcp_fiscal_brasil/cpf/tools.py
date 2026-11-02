"""Ferramentas MCP para CPF."""

from .client import CPFClient, validate_cpf
from .schemas import CPFCadastro, CPFValidation

_client = CPFClient()


async def validar_cpf_tool(cpf: str) -> CPFValidation:
    """
    Valida o dígito verificador de um CPF brasileiro.

    Não consulta APIs externas - apenas verifica o cálculo matemático.
    A Receita Federal não disponibiliza API pública para consulta de dados de CPF.

    Args:
        cpf: Número do CPF com ou sem formatação (ex: '123.456.789-09' ou '12345678909')

    Returns:
        CPFValidation indicando se o CPF é matematicamente válido.
    """
    return validate_cpf(cpf)


async def consultar_cpf_tool(cpf: str) -> CPFCadastro:
    """
    Consulta a situação cadastral de um CPF na Receita Federal (premium, opt-in).

    Finalidade fiscal: conferir o destinatário de NF-e/NFC-e ou o tomador de NFS-e
    (pessoa física) antes de emitir o documento. Não é uma ferramenta de localização
    de pessoas. Emitir para CPF cancelado por óbito, nulo ou cancelado de ofício gera
    documento fiscal com destinatário inválido e passivo para o emitente.

    Requer o provedor premium opcional cpfcnpj.com.br (CPFCNPJ_TOKEN): não existe fonte
    gratuita de situação cadastral de CPF. O dígito verificador é validado localmente
    antes de qualquer chamada, para não gastar crédito com CPF malformado. O pacote é
    definido por CPFCNPJ_CPF_PACKET (padrão 26: nome, nascimento e situação).

    Privacidade: o CPF é mascarado em todo log (***.***.***-XX); o PDF do comprovante
    (pacote 8) nunca passa por log; campos operacionais do provedor (saldo, consultaID,
    pacote usado) não são retornados.

    Args:
        cpf: Número do CPF com ou sem formatação (ex: '123.456.789-09' ou '12345678909').

    Returns:
        CPFCadastro com situação cadastral, descrição oficial e o derivado apto_emissao
        (verdadeiro apenas quando a situação é Regular).

    Raises:
        ValueError: Se o CPF for inválido (dígito verificador).
    """
    if not validate_cpf(cpf).válido:
        raise ValueError(f"CPF inválido: {cpf}. Verifique os 11 dígitos e o dígito verificador.")
    return await _client.consultar(cpf)
