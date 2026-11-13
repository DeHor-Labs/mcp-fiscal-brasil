"""Funções de tool para o módulo MEI."""

from mcp_fiscal_brasil._core import get_logger
from mcp_fiscal_brasil.shared.validators import normalizar_cnpj, validate_cnpj_qualquer

from .client import MEIClient
from .regularizacao import orientar_regularizacao_mei as _orientar_regularizacao_mei
from .schemas import MEIStatus, RegularizacaoMeiRequest, RegularizacaoMeiResponse

logger = get_logger(__name__)

_client = MEIClient()


async def consultar_status_mei(cnpj: str) -> MEIStatus:
    if not validate_cnpj_qualquer(cnpj):
        raise ValueError(
            f"CNPJ inválido: '{cnpj}'. "
            "Verifique o formato e o dígito verificador (ex: '11.222.333/0001-81')."
        )
    cnpj_norm = normalizar_cnpj(cnpj)
    logger.info("tool_consultar_status_mei_called", cnpj_prefixo=cnpj_norm[:8] + "****")
    return await _client.get_mei_status(cnpj_norm)


async def orientar_regularizacao_mei(
    cnpj: str | None = None,
    anos_omitidos: list[int] | None = None,
    receita_zero: bool = True,
) -> RegularizacaoMeiResponse:
    request = RegularizacaoMeiRequest(
        cnpj=cnpj,
        anos_omitidos=anos_omitidos,
        receita_zero=receita_zero,
    )
    logger.info(
        "tool_orientar_regularizacao_mei_called",
        tem_cnpj=bool(cnpj),
        anos=anos_omitidos or [],
    )
    return _orientar_regularizacao_mei(request)
