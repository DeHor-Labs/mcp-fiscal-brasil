"""Cliente BCB - consulta séries temporais do SGS e cotações PTAX."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp_fiscal_brasil._core import FiscalNotFoundError, HTTPClient, get_logger, settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError

from .schemas import CorrecaoMonetariaResponse, PTAXResponse, SerieBCB

logger = get_logger(__name__)

# Séries SGS do BCB
_SERIE_SELIC = 11  # Taxa Selic efetiva diária
_SERIE_IPCA = 433  # IPCA acumulado mensal (%)

# Base OData para cotações PTAX
_PTAX_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"


class BCBClient:
    """Cliente para a API SGS do Banco Central do Brasil e cotações PTAX."""

    def _http_client(self, base_url: str | None = None) -> HTTPClient:
        url = base_url or settings.bcb_sgs_base_url
        return HTTPClient(
            url,
            timeout=settings.mcp_fiscal_http_timeout,
            max_retries=settings.mcp_fiscal_max_retries,
            cache_ttl=settings.mcp_fiscal_cache_ttl,
            rate_limit_per_second=5,
        )

    def _format_date(self, d: date) -> str:
        """Formata data no padrão dd/MM/yyyy esperado pelo SGS."""
        return d.strftime("%d/%m/%Y")

    def _parse_serie(self, data: list[Any]) -> list[SerieBCB]:
        """Converte lista de dicionários SGS em objetos SerieBCB."""
        result = []
        for item in data:
            raw_date = item.get("data", "")
            raw_valor = item.get("valor", "")
            if not raw_date or not raw_valor:
                continue
            try:
                # SGS retorna datas no formato dd/MM/yyyy
                day, month, year = raw_date.split("/")
                parsed_date = date(int(year), int(month), int(day))
                parsed_valor = float(raw_valor.replace(",", "."))
                result.append(SerieBCB(data=parsed_date, valor=parsed_valor))
            except (ValueError, AttributeError):
                continue
        return result

    async def taxa_selic(
        self,
        data_inicio: date,
        data_fim: date | None = None,
    ) -> list[SerieBCB]:
        """Consulta a taxa Selic efetiva diária (SGS série 11)."""
        logger.info("bcb_taxa_selic_started", data_inicio=str(data_inicio), data_fim=str(data_fim))
        return await self._consultar_serie(
            serie_id=_SERIE_SELIC,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

    async def ipca_periodo(
        self,
        data_inicio: date,
        data_fim: date | None = None,
    ) -> list[SerieBCB]:
        """Consulta o IPCA acumulado mensal (SGS série 433)."""
        logger.info(
            "bcb_ipca_periodo_started", data_inicio=str(data_inicio), data_fim=str(data_fim)
        )
        return await self._consultar_serie(
            serie_id=_SERIE_IPCA,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

    async def _consultar_serie(
        self,
        serie_id: int,
        data_inicio: date,
        data_fim: date | None,
    ) -> list[SerieBCB]:
        """Consulta uma série SGS genérica por código e período."""
        fim = data_fim or date.today()
        params = {
            "formato": "json",
            "dataInicial": self._format_date(data_inicio),
            "dataFinal": self._format_date(fim),
        }
        path = f"/bcdata.sgs.{serie_id}/dados"

        async with self._http_client() as client:
            try:
                raw = await client.get_list(path, params=params)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"Série BCB {serie_id} não encontrada", "Recurso", str(serie_id)
                    ) from exc
                raise

        series = self._parse_serie(raw)
        if not series:
            raise FiscalNotFoundError(
                f"Nenhum dado encontrado para a série BCB {serie_id} no período informado",
                "Recurso",
                str(serie_id),
            )
        return series

    async def ptax_data(self, data: date, moeda: str = "USD") -> PTAXResponse:
        """Consulta a cotação PTAX (compra/venda) para uma data e moeda específicas."""
        import re

        moeda_norm = moeda.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", moeda_norm):
            from mcp_fiscal_brasil._core import FiscalValidationError

            raise FiscalValidationError(
                f"Código de moeda inválido: '{moeda}'. "
                "Informe o código ISO 4217 com 3 letras (ex: 'USD', 'EUR', 'BRL').",
                field="moeda",
                value=moeda,
            )
        logger.info("bcb_ptax_data_started", data=str(data), moeda=moeda_norm)
        date_str = data.strftime("%m-%d-%Y")  # OData usa MM-dd-yyyy
        # moeda_norm contém apenas [A-Z]{3} - seguro para interpolação na URL OData
        path = (
            f"/CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)"
            f"?@moeda='{moeda_norm}'&@dataCotacao='{date_str}'&$format=json"
        )

        async with self._http_client(_PTAX_BASE_URL) as client:
            try:
                raw = await client.get(path)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"Cotação PTAX para {moeda} em {data} não encontrada",
                        "Recurso",
                        moeda,
                    ) from exc
                raise

        items: list[Any] = raw.get("value", [])
        if not items:
            raise FiscalNotFoundError(
                f"Cotação PTAX para {moeda} em {data} não encontrada (dia sem cotação, "
                "verifique se é dia útil)",
                "Recurso",
                moeda,
            )
        item = items[0]
        return PTAXResponse(
            data=data,
            moeda=moeda,
            compra=float(item.get("cotacaoCompra", 0)),
            venda=float(item.get("cotacaoVenda", 0)),
        )

    async def calcular_correcao_monetaria(
        self,
        valor: float,
        data_inicio: date,
        data_fim: date,
        indice: str = "IPCA",
    ) -> CorrecaoMonetariaResponse:
        """Calcula a correção monetária de um valor entre duas datas usando IPCA ou Selic."""
        logger.info(
            "bcb_correcao_monetaria_started",
            valor=valor,
            data_inicio=str(data_inicio),
            data_fim=str(data_fim),
            indice=indice,
        )
        indice_upper = indice.upper()
        if indice_upper == "IPCA":
            serie = await self.ipca_periodo(data_inicio, data_fim)
        elif indice_upper == "SELIC":
            serie = await self.taxa_selic(data_inicio, data_fim)
        else:
            raise ValueError(f"Índice '{indice}' não suportado. Use 'IPCA' ou 'SELIC'.")

        # Calcula fator acumulado: produto de (1 + taxa/100) para cada período
        fator = 1.0
        for ponto in serie:
            fator *= 1.0 + ponto.valor / 100.0

        valor_corrigido = round(valor * fator, 2)
        return CorrecaoMonetariaResponse(
            valor_original=valor,
            data_inicio=data_inicio,
            data_fim=data_fim,
            indice=indice_upper,
            fator_acumulado=round(fator, 8),
            valor_corrigido=valor_corrigido,
        )
