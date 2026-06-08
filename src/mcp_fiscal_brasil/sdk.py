"""
MCP Fiscal Brasil - SDK para integração direta em aplicações Python.

Permite usar todas as funcionalidades fiscais como biblioteca Python,
sem precisar rodar o servidor MCP.

Uso básico:

    from mcp_fiscal_brasil import FiscalBrasil

    fiscal = FiscalBrasil()

    # Consultar CNPJ
    empresa = await fiscal.consultar_cnpj("00.000.000/0001-91")
    print(empresa.razao_social)

    # Validar CPF
    válido = fiscal.validar_cpf("123.456.789-09")

    # Status SEFAZ
    status = await fiscal.status_sefaz("SP")

Uso como context manager (recomendado para múltiplas consultas):

    async with FiscalBrasil() as fiscal:
        empresa = await fiscal.consultar_cnpj("33.000.167/0001-01")
        simples = await fiscal.consultar_simples("33.000.167/0001-01")
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any

from .cnpj.client import CNPJClient
from .cnpj.schemas import CNPJResponse
from .nfe.client import NFEClient
from .nfe.schemas import NFeResponse, StatusSEFAZResponse
from .shared.validators import validate_chave_nfe, validate_cnpj, validate_cpf
from .simples.client import SimplesClient
from .simples.schemas import SimplesStatus


class FiscalBrasil:
    """
    Interface unificada para consultas fiscais brasileiras.

    Encapsula todos os clientes do pacote (CNPJ, NFe, Simples Nacional,
    eSocial, SPED, NFSe) em um único ponto de entrada.

    Pode ser usada como context manager assíncrono para garantir o
    encerramento correto de recursos de rede:

        async with FiscalBrasil() as fiscal:
            empresa = await fiscal.consultar_cnpj("33000167000101")

    Ou instanciada diretamente quando o ciclo de vida é gerenciado
    externamente (ex: variável de módulo em FastAPI):

        fiscal = FiscalBrasil()
        empresa = await fiscal.consultar_cnpj("33000167000101")
    """

    def __init__(self) -> None:
        self._cnpj_client = CNPJClient()
        self._nfe_client = NFEClient()
        self._simples_client = SimplesClient()

    # ------------------------------------------------------------------
    # Context manager assíncrono
    # ------------------------------------------------------------------

    async def __aenter__(self) -> FiscalBrasil:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.fechar()

    async def fechar(self) -> None:
        """Encerra recursos de rede (conexões HTTP). Opcional quando usado como variável global."""
        # Os clientes criam e fecham conexões por chamada via context manager interno,
        # portanto não há recursos persistentes a liberar nesta versão.
        # Este método existe para compatibilidade futura e para uso explícito.

    # ------------------------------------------------------------------
    # CNPJ
    # ------------------------------------------------------------------

    async def consultar_cnpj(self, cnpj: str) -> CNPJResponse:
        """
        Consulta os dados de um CNPJ na Receita Federal.

        Tenta BrasilAPI primeiro; em caso de falha, usa ReceitaWS como
        fallback automático.

        Args:
            cnpj: CNPJ com ou sem máscara (ex: "33.000.167/0001-01" ou "33000167000101").

        Returns:
            CNPJResponse com razão social, endereço, CNAE, QSA e mais.

        Raises:
            ValueError: Se o CNPJ for inválido.
            Exception: Se todas as APIs externas falharem.

        Exemplo:
            empresa = await fiscal.consultar_cnpj("33.000.167/0001-01")
            print(empresa.razao_social)  # "PETROLEO BRASILEIRO S A PETROBRAS"
        """
        if not validate_cnpj(cnpj):
            raise ValueError(f"CNPJ inválido: {cnpj}")
        return await self._cnpj_client.consultar(cnpj)

    def validar_cnpj(self, cnpj: str) -> bool:
        """
        Valida o dígito verificador de um CNPJ (offline, sem chamada de API).

        Args:
            cnpj: CNPJ com ou sem máscara.

        Returns:
            True se o CNPJ for matematicamente válido, False caso contrário.

        Exemplo:
            fiscal.validar_cnpj("33.000.167/0001-01")  # True
            fiscal.validar_cnpj("11.111.111/1111-11")  # False
        """
        return validate_cnpj(cnpj)

    # ------------------------------------------------------------------
    # CPF
    # ------------------------------------------------------------------

    def validar_cpf(self, cpf: str) -> bool:
        """
        Valida o dígito verificador de um CPF (offline, sem chamada de API).

        A Receita Federal não disponibiliza API pública para consulta de CPF.
        Esta validação verifica apenas o cálculo do dígito verificador.

        Args:
            cpf: CPF com ou sem máscara (ex: "529.982.247-25" ou "52998224725").

        Returns:
            True se o CPF for matematicamente válido, False caso contrário.

        Exemplo:
            fiscal.validar_cpf("529.982.247-25")  # True
            fiscal.validar_cpf("111.111.111-11")  # False (sequência repetida)
        """
        return validate_cpf(cpf)

    # ------------------------------------------------------------------
    # NFe
    # ------------------------------------------------------------------

    async def consultar_nfe(self, chave: str) -> NFeResponse:
        """
        Consulta os dados de uma NFe pela chave de acesso de 44 dígitos.

        Cadeia de fallback automática:
          1. BrasilAPI
          2. Portal Nacional NFe (SEFAZ federal)
          3. Dados parciais extraídos da própria chave

        Args:
            chave: Chave de acesso da NFe com 44 dígitos numéricos.

        Returns:
            NFeResponse com emitente, destinatário, itens, totais e situação.

        Raises:
            ValueError: Se a chave de acesso for inválida.

        Exemplo:
            nfe = await fiscal.consultar_nfe("35230112345678901234550010000000011000000018")
            print(nfe.situacao)
        """
        if not validate_chave_nfe(chave):
            raise ValueError(f"Chave de acesso NFe inválida: {chave}")
        return await self._nfe_client.consultar_por_chave(chave)

    def validar_chave_nfe(self, chave: str) -> dict[str, Any]:
        """
        Valida e extrai os campos estruturais de uma chave de acesso NFe/NFCe.

        A validação verifica o dígito verificador pelo módulo 11 (offline).
        A extração decodifica os campos embutidos na chave (UF, CNPJ, série, etc.).

        Args:
            chave: Chave de acesso com 44 dígitos numéricos.

        Returns:
            Dicionário com campos extraídos:
            - válida (bool): Se o dígito verificador é correto.
            - uf (str): UF de emissão.
            - ano_mes (str): Ano/mês de emissão no formato MM/AAAA.
            - cnpj_emitente (str): CNPJ do emitente (14 dígitos).
            - modelo (str): Modelo do documento ("55"=NFe, "65"=NFCe).
            - serie (str): Série da nota.
            - número (str): Número da nota fiscal.

        Exemplo:
            info = fiscal.validar_chave_nfe("35230112345678901234550010000000011000000018")
            print(info["uf"])          # "SP"
            print(info["cnpj_emitente"])  # "12345678901234"
        """
        from .shared.constants import CODIGO_UF

        números = "".join(c for c in chave if c.isdigit())
        válida = validate_chave_nfe(chave)

        if len(números) != 44:
            return {"válida": False, "erro": f"Chave deve ter 44 dígitos, recebeu {len(números)}"}

        cod_uf = int(números[:2])
        return {
            "válida": válida,
            "uf": CODIGO_UF.get(cod_uf, f"UF {cod_uf}"),
            "ano_mes": f"{números[4:6]}/{números[2:4]}",
            "cnpj_emitente": números[6:20],
            "modelo": números[20:22],
            "serie": números[22:25],
            "número": números[25:34],
            "tipo_emissao": números[34],
            "codigo_numerico": números[35:43],
            "digito_verificador": números[43],
        }

    async def status_sefaz(self, uf: str, ambiente: str = "producao") -> StatusSEFAZResponse:
        """
        Consulta o status do serviço SEFAZ de uma UF.

        Usa BrasilAPI como proxy para o webservice do SEFAZ estadual.
        Em caso de falha, retorna status "Indisponível".

        Args:
            uf: Sigla do estado (ex: "SP", "RJ", "MG"). Não diferencia maiúsculas.
            ambiente: "producao" ou "homologacao" (padrão: "producao").

        Returns:
            StatusSEFAZResponse com status, descrição e código de retorno.

        Exemplo:
            status = await fiscal.status_sefaz("SP")
            print(status.status)   # "Em Operação"
        """
        return await self._nfe_client.consultar_status_servico(uf, ambiente)

    # ------------------------------------------------------------------
    # Simples Nacional
    # ------------------------------------------------------------------

    async def consultar_simples(self, cnpj: str) -> SimplesStatus:
        """
        Consulta a situação de um CNPJ no Simples Nacional e MEI.

        Args:
            cnpj: CNPJ com ou sem máscara.

        Returns:
            SimplesStatus com optante_simples, optante_mei e datas de opção/exclusão.

        Raises:
            ValueError: Se o CNPJ for inválido.

        Exemplo:
            simples = await fiscal.consultar_simples("33.000.167/0001-01")
            print(simples.simples_nacional)  # False (Petrobras não é optante)
            print(simples.mei)      # False
        """
        if not validate_cnpj(cnpj):
            raise ValueError(f"CNPJ inválido: {cnpj}")
        return await self._simples_client.get_simples_status(cnpj)

    # ------------------------------------------------------------------
    # SPED
    # ------------------------------------------------------------------

    async def analisar_sped(self, conteudo: str, nome_arquivo: str | None = None) -> dict[str, Any]:
        """
        Analisa um arquivo SPED e extrai informações estruturais.

        Suporta EFD-ICMS/IPI, EFD-Contribuições, ECD e ECF.
        O arquivo deve ser passado como string (conteúdo completo no formato pipe-delimitado).

        Args:
            conteudo: Conteúdo do arquivo SPED como string.
            nome_arquivo: Nome do arquivo (opcional, usado apenas para log).

        Returns:
            Dicionário com:
            - tipo_sped (str): Tipo identificado ("EFD-ICMS-IPI", "EFD-Contribuições", etc.)
            - abertura (dict | None): Dados do registro 0000 (empresa, CNPJ, UF).
            - resumo (dict): Período, total de registros e contagem por tipo.
            - erros (list[str]): Erros encontrados na estrutura.
            - avisos (list[str]): Avisos sobre o arquivo.

        Exemplo:
            with open("sped.txt") as f:
                conteudo = f.read()
            resultado = await fiscal.analisar_sped(conteudo)
            print(resultado["tipo_sped"])  # "EFD-ICMS-IPI"
        """
        from .sped.tools import analisar_sped

        resposta = await analisar_sped(conteudo, nome_arquivo)
        return resposta.model_dump()

    # ------------------------------------------------------------------
    # NFSe
    # ------------------------------------------------------------------

    async def portal_nfse(self, municipio: str, uf: str) -> dict[str, str]:
        """
        Retorna o portal de consulta de NFSe para um município.

        NFSe não possui padrão nacional único; cada município tem seu sistema
        (ABRASF, ISS.net, Betha, Curitiba, etc.). Este método localiza o portal
        correto para o município informado e, quando não encontrado, retorna
        o Portal Nacional ABRASF como alternativa.

        Args:
            municipio: Nome do município (ex: "São Paulo", "Belo Horizonte").
            uf: Sigla do estado (ex: "SP", "MG").

        Returns:
            Dicionário com:
            - portal_municipio (str): URL do portal de consulta.
            - sistema_nfse (str): Sistema utilizado (ABRASF, ISS.net, etc.)
            - alternativa (str): Alternativa para integração automatizada.
            - status (str): "consulta_manual_necessaria".

        Exemplo:
            portal = await fiscal.portal_nfse("São Paulo", "SP")
            print(portal["portal_municipio"])  # URL da prefeitura de SP
            print(portal["sistema_nfse"])      # "ABRASF"
        """
        from .nfse.tools import consultar_nfse

        resultado = await consultar_nfse(
            numero="",
            municipio=municipio,
            uf=uf,
        )
        return resultado

    # ------------------------------------------------------------------
    # eSocial
    # ------------------------------------------------------------------

    async def listar_eventos_esocial(self, grupo: str | None = None) -> list[dict[str, Any]]:
        """
        Lista os eventos do eSocial, com opção de filtro por grupo.

        Args:
            grupo: Filtrar por grupo do evento. Valores válidos:
                   "Tabelas", "Não Periodicos", "Periodicos",
                   "Exclusao", "Totalizadores".
                   Se None, retorna todos os 45+ eventos catalogados.

        Returns:
            Lista de dicionários com campos:
            - código (str): Código do evento (ex: "S-2200").
            - nome (str): Nome completo do evento.
            - grupo (str): Grupo ao qual pertence.
            - descrição (str): Descrição do propósito do evento.

        Exemplo:
            eventos = await fiscal.listar_eventos_esocial("Periodicos")
            for e in eventos:
                print(f"{e['código']}: {e['nome']}")
        """
        from .esocial.tools import listar_eventos_esocial

        eventos = await listar_eventos_esocial(grupo)
        return [e.model_dump() for e in eventos]

    # ------------------------------------------------------------------
    # Métodos síncronos (wrappers com asyncio.run)
    # ------------------------------------------------------------------

    def consultar_cnpj_sync(self, cnpj: str) -> CNPJResponse:
        """
        Versão síncrona de consultar_cnpj. Útil em contextos não-async (Django, scripts).

        Não use dentro de um event loop já ativo (ex: FastAPI, Jupyter).
        Prefira o método assíncrono nesses casos.

        Args:
            cnpj: CNPJ com ou sem máscara.

        Returns:
            CNPJResponse com os dados da empresa.
        """
        return asyncio.run(self.consultar_cnpj(cnpj))

    def consultar_simples_sync(self, cnpj: str) -> SimplesStatus:
        """
        Versão síncrona de consultar_simples. Útil em contextos não-async.

        Args:
            cnpj: CNPJ com ou sem máscara.

        Returns:
            SimplesNacionalResponse com situação no Simples Nacional.
        """
        return asyncio.run(self.consultar_simples(cnpj))

    def status_sefaz_sync(self, uf: str, ambiente: str = "producao") -> StatusSEFAZResponse:
        """
        Versão síncrona de status_sefaz. Útil em contextos não-async.

        Args:
            uf: Sigla do estado.
            ambiente: "producao" ou "homologacao".

        Returns:
            StatusSEFAZResponse com status do serviço.
        """
        return asyncio.run(self.status_sefaz(uf, ambiente))
