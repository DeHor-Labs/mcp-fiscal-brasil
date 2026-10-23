"""Cliente para consulta de CNPJ via BrasilAPI e ReceitaWS.

Quando o provedor premium opcional cpfcnpj.com.br esta configurado (token via
``CPFCNPJ_TOKEN``), ele e tentado primeiro, com dados oficiais em tempo real, e
as fontes gratuitas (BrasilAPI e ReceitaWS) seguem como fallback. Sem token, o
comportamento e identico ao anterior: apenas as fontes gratuitas sao usadas.
"""

from datetime import date
from typing import Any

from mcp_fiscal_brasil._core import FiscalError, HTTPClient, Settings, get_logger

from ..shared import cpfcnpj as cpfcnpj_provider
from ..shared.schemas import Endereco
from ..shared.validators import normalizar_cnpj
from .schemas import AtividadeCNAE, CNPJResponse, QSASocio

logger = get_logger(__name__)
_settings = Settings()


def _parse_data(valor: str | None) -> date | None:
    """Converte datas em ISO (AAAA-MM-DD) ou no formato brasileiro (DD/MM/AAAA)."""
    if not valor:
        return None
    texto = valor.strip()
    for formato in ("iso", "%d/%m/%Y"):
        try:
            if formato == "iso":
                return date.fromisoformat(texto[:10])
            from datetime import datetime

            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


class CNPJClient:
    """Cliente para busca de dados de CNPJ em fontes publicas."""

    def _http_client(self, base_url: str) -> HTTPClient:
        return HTTPClient(
            base_url,
            timeout=_settings.mcp_fiscal_http_timeout,
            max_retries=_settings.mcp_fiscal_max_retries,
            cache_ttl=_settings.mcp_fiscal_cache_ttl,
            rate_limit_per_second=_settings.mcp_fiscal_rate_limit,
        )

    async def consultar(self, cnpj: str) -> CNPJResponse:
        """
        Consulta os dados de um CNPJ.

        Quando o provedor premium cpfcnpj.com.br esta configurado, ele e tentado
        primeiro. Em seguida, tenta BrasilAPI e, por fim, ReceitaWS.

        Suporte a CNPJ alfanumerico (IN RFB 2.229/2024, vigencia jul/2026) por
        provedor:
        - cpfcnpj.com.br: aceita o formato alfanumerico no caminho da URL
          (confirmado pelo provedor).
        - BrasilAPI: aceita, pois apenas faz proxy para o projeto minha-receita,
          que valida o CNPJ com a lib go-cnpj (com tratamento alfanumerico).
          Ref.: BrasilAPI issues #789 e #827 (fechadas) e services/cnpj.js
          (repassa o parametro sem remover letras).
        - ReceitaWS: a documentacao publica nao confirma suporte ao formato
          alfanumerico; por isso NAO usamos essa fonte como fallback quando o
          CNPJ contem letras, evitando respostas incorretas.
        """
        # Normaliza removendo mascara e preservando letras: o CNPJ alfanumerico
        # (IN RFB 2.229/2024, vigencia jul/2026) tem 12 posicoes alfanumericas
        # seguidas de 2 digitos verificadores. Usar isdigit() aqui descartaria as
        # letras e quebraria a consulta. normalizar_cnpj remove separadores e
        # mantem A-Z (em maiusculas), aceito pela cpfcnpj.com.br no caminho da URL.
        cnpj_limpo = normalizar_cnpj(cnpj)
        alfanumerico = bool(cnpj_limpo) and not cnpj_limpo.isdigit()
        logger.info("cnpj_lookup_started", cnpj=cnpj_limpo, alfanumerico=alfanumerico)

        if cpfcnpj_provider.provedor_configurado():
            try:
                return await self._consultar_cpfcnpj(cnpj_limpo)
            except Exception as exc:
                logger.warning(
                    "cpfcnpj_cnpj_lookup_failed",
                    cnpj=cnpj_limpo,
                    error=str(exc),
                    fallback="brasilapi",
                )

        try:
            return await self._consultar_brasil_api(cnpj_limpo)
        except Exception as exc:
            if alfanumerico:
                # ReceitaWS nao tem suporte documentado a CNPJ alfanumerico:
                # nao fazemos fallback para nao devolver dados incorretos.
                logger.warning(
                    "receitaws_skip_alfanumerico",
                    cnpj=cnpj_limpo,
                    error=str(exc),
                )
                raise FiscalError(
                    "CNPJ alfanumérico não obtido na BrasilAPI e a ReceitaWS não "
                    "atende o formato alfanumérico (IN RFB 2.229/2024). Configure o "
                    "provedor cpfcnpj.com.br (CPFCNPJ_TOKEN) para consultas alfanuméricas."
                ) from exc
            logger.warning(
                "brasilapi_cnpj_lookup_failed",
                cnpj=cnpj_limpo,
                error=str(exc),
                fallback="receitaws",
            )
            return await self._consultar_receita_ws(cnpj_limpo)

    async def _consultar_cpfcnpj(self, cnpj: str) -> CNPJResponse:
        data = await cpfcnpj_provider.consultar(_settings.cpfcnpj_cnpj_packet, cnpj)
        return self._parse_cpfcnpj(data, cnpj)

    async def _consultar_brasil_api(self, cnpj: str) -> CNPJResponse:
        async with self._http_client(_settings.brasilapi_base_url) as client:
            data = await client.get(f"/cnpj/v1/{cnpj}")
        return self._parse_brasil_api(data, cnpj)

    async def _consultar_receita_ws(self, cnpj: str) -> CNPJResponse:
        async with self._http_client(_settings.receita_base_url) as client:
            data = await client.get(f"/cnpj/{cnpj}")
        return self._parse_receita_ws(data, cnpj)

    def _parse_brasil_api(self, data: dict[str, Any], cnpj: str) -> CNPJResponse:
        """Transforma resposta da BrasilAPI em CNPJResponse."""
        atividade_principal = None
        if data.get("cnae_fiscal") and data.get("cnae_fiscal_descricao"):
            atividade_principal = AtividadeCNAE(
                código=str(data["cnae_fiscal"]),
                descrição=data["cnae_fiscal_descricao"],
            )

        atividades_secundarias = []
        for cnae in data.get("cnaes_secundarios") or []:
            if cnae.get("código") and cnae.get("descrição"):
                atividades_secundarias.append(
                    AtividadeCNAE(código=str(cnae["código"]), descrição=cnae["descrição"])
                )

        endereco = Endereco(
            logradouro=data.get("logradouro"),
            número=data.get("número"),
            complemento=data.get("complemento"),
            bairro=data.get("bairro"),
            municipio=data.get("municipio"),
            uf=data.get("uf"),
            cep=data.get("cep"),
        )

        qsa = []
        for sócio in data.get("qsa") or []:
            qsa.append(
                QSASocio(
                    nome=sócio.get("nome_socio", ""),
                    qualificacao=sócio.get("qualificacao_socio", ""),
                    cpf_cnpj_socio=sócio.get("cnpj_cpf_do_socio"),
                    faixa_etaria=sócio.get("faixa_etaria"),
                )
            )

        data_abertura = None
        if data.get("data_inicio_atividade"):
            try:
                data_abertura = date.fromisoformat(data["data_inicio_atividade"])
            except ValueError:
                pass

        return CNPJResponse(
            cnpj=cnpj,
            razao_social=data.get("razao_social", ""),
            nome_fantasia=data.get("nome_fantasia") or None,
            situacao_cadastral=data.get("descricao_situacao_cadastral", ""),
            natureza_juridica=data.get("natureza_juridica", ""),
            porte=data.get("porte"),
            capital_social=data.get("capital_social"),
            data_abertura=data_abertura,
            atividade_principal=atividade_principal,
            atividades_secundarias=atividades_secundarias,
            endereco=endereco,
            telefone=data.get("ddd_telefone_1"),
            email=data.get("email"),
            qsa=qsa,
            origem="BrasilAPI",
        )

    def _parse_receita_ws(self, data: dict[str, Any], cnpj: str) -> CNPJResponse:
        """Transforma resposta da ReceitaWS em CNPJResponse."""
        atividade_principal = None
        for ativ in data.get("atividade_principal") or []:
            atividade_principal = AtividadeCNAE(
                código=ativ.get("code", ""),
                descrição=ativ.get("text", ""),
            )
            break

        atividades_secundarias = [
            AtividadeCNAE(código=a.get("code", ""), descrição=a.get("text", ""))
            for a in data.get("atividades_secundarias") or []
        ]

        endereco = Endereco(
            logradouro=data.get("logradouro"),
            número=data.get("número"),
            complemento=data.get("complemento"),
            bairro=data.get("bairro"),
            municipio=data.get("municipio"),
            uf=data.get("uf"),
            cep=data.get("cep"),
        )

        qsa = [
            QSASocio(
                nome=s.get("nome", ""),
                qualificacao=s.get("qual", ""),
            )
            for s in data.get("qsa") or []
        ]

        return CNPJResponse(
            cnpj=cnpj,
            razao_social=data.get("nome", ""),
            nome_fantasia=data.get("fantasia") or None,
            situacao_cadastral=data.get("situacao", ""),
            natureza_juridica=data.get("natureza_juridica", ""),
            porte=data.get("porte"),
            capital_social=None,
            atividade_principal=atividade_principal,
            atividades_secundarias=atividades_secundarias,
            endereco=endereco,
            telefone=data.get("telefone"),
            email=data.get("email"),
            qsa=qsa,
            origem="ReceitaWS",
        )

    def _parse_cpfcnpj(self, data: dict[str, Any], cnpj: str) -> CNPJResponse:
        """Transforma a resposta do pacote CNPJ da cpfcnpj.com.br em CNPJResponse."""
        cnae = data.get("cnae") or {}
        atividade_principal = None
        if cnae.get("fiscal") and cnae.get("descricao"):
            atividade_principal = AtividadeCNAE(
                código=str(cnae["fiscal"]),
                descrição=cnae["descricao"],
            )

        atividades_secundarias = []
        for sec in cnae.get("secundarias") or []:
            codigo = sec.get("subclasse") or sec.get("id")
            if codigo and sec.get("descricao"):
                atividades_secundarias.append(
                    AtividadeCNAE(código=str(codigo), descrição=sec["descricao"])
                )

        endereco_raw = data.get("matrizEndereco") or {}
        endereco = Endereco(
            logradouro=endereco_raw.get("logradouro"),
            número=endereco_raw.get("numero"),
            complemento=endereco_raw.get("complemento"),
            bairro=endereco_raw.get("bairro"),
            municipio=endereco_raw.get("cidade"),
            uf=endereco_raw.get("uf"),
            cep=endereco_raw.get("cep"),
        )

        qsa = []
        for sócio in data.get("socios") or []:
            qsa.append(
                QSASocio(
                    nome=sócio.get("nome", ""),
                    qualificacao=self._qualificacao_texto(sócio.get("qualificacao_socio")),
                    cpf_cnpj_socio=sócio.get("cpf_cnpj_socio"),
                    faixa_etaria=sócio.get("faixa_etaria"),
                    nome_representante_legal=sócio.get("nome_representante"),
                    qualificacao_representante_legal=self._qualificacao_texto(
                        sócio.get("qualificacao_representante")
                    ),
                )
            )

        natureza = data.get("naturezaJuridica") or {}
        natureza_texto = " - ".join(
            parte for parte in (natureza.get("codigo"), natureza.get("descricao")) if parte
        )

        telefone = None
        for tel in data.get("telefones") or []:
            ddd = tel.get("ddd")
            numero = tel.get("numero")
            if ddd and numero:
                telefone = f"({ddd}) {numero}"
                break
            if numero:
                telefone = numero
                break

        situacao = data.get("situacao") or {}
        simples = data.get("simplesNacional") or {}
        porte = data.get("porte") or {}

        return CNPJResponse(
            cnpj=cnpj,
            razao_social=data.get("razao", ""),
            nome_fantasia=data.get("fantasia") or None,
            situacao_cadastral=situacao.get("nome", ""),
            data_situacao_cadastral=_parse_data(situacao.get("data")),
            natureza_juridica=natureza_texto,
            porte=porte.get("descricao"),
            capital_social=data.get("capitalSocial"),
            data_abertura=_parse_data(data.get("inicioAtividade")),
            atividade_principal=atividade_principal,
            atividades_secundarias=atividades_secundarias,
            endereco=endereco,
            telefone=telefone,
            email=data.get("email"),
            qsa=qsa,
            simples_nacional=self._sim_nao(simples.get("optante")),
            mei=self._sim_nao(simples.get("mei")),
            opcao_simples=simples or None,
            origem="cpfcnpj.com.br",
        )

    @staticmethod
    def _sim_nao(valor: Any) -> bool | None:
        """Converte um campo textual 'Sim'/'Nao' em booleano; None se ausente."""
        if not isinstance(valor, str) or not valor.strip():
            return None
        return valor.strip().lower().startswith("s")

    @staticmethod
    def _qualificacao_texto(valor: Any) -> str:
        """Extrai a descricao de uma qualificacao que pode vir como texto ou objeto."""
        if isinstance(valor, dict):
            return str(valor.get("descricao") or valor.get("nome") or "")
        if isinstance(valor, str):
            return valor
        return ""
