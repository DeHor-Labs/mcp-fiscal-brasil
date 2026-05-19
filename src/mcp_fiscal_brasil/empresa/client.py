import asyncio

from mcp_fiscal_brasil._core import get_logger
from mcp_fiscal_brasil.cnpj.client import CNPJClient
from mcp_fiscal_brasil.simples.client import SimplesClient

from .schemas import EmpresaInfo

logger = get_logger(__name__)


class EmpresaClient:
    """Cliente que compõe dados de CNPJ e Simples Nacional."""

    def __init__(self) -> None:
        self.cnpj_client = CNPJClient()
        self.simples_client = SimplesClient()

    async def get_empresa(self, cnpj: str) -> EmpresaInfo:
        """Busca dados enriquecidos da empresa cruzando CNPJ e Simples."""
        logger.info("empresa_info_started", cnpj=cnpj)

        cnpj_data_task = self.cnpj_client.consultar(cnpj)
        simples_data_task = self.simples_client.get_simples_status(cnpj)

        # Executa as chamadas em paralelo
        results = await asyncio.gather(cnpj_data_task, simples_data_task, return_exceptions=True)
        cnpj_data, simples_data = results[0], results[1]

        if isinstance(cnpj_data, BaseException):
            # CNPJ é o dado primário, se falhar, propagamos o erro
            raise cnpj_data

        simples_nacional = False
        mei = False
        if not isinstance(simples_data, BaseException):
            simples_nacional = simples_data.simples_nacional
            mei = simples_data.mei
        else:
            logger.warning("empresa_simples_fetch_failed", cnpj=cnpj, error=str(simples_data))

        return EmpresaInfo(
            cnpj=cnpj_data.cnpj,
            razao_social=cnpj_data.razao_social,
            nome_fantasia=cnpj_data.nome_fantasia,
            situacao=cnpj_data.situacao_cadastral,
            porte=cnpj_data.porte,
            natureza_juridica=cnpj_data.natureza_juridica,
            simples_nacional=simples_nacional,
            mei=mei,
            atividade_principal=cnpj_data.atividade_principal,
            atividades_secundarias=cnpj_data.atividades_secundarias,
            endereco=cnpj_data.endereco,
        )
