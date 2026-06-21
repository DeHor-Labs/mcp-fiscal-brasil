"""
Exemplo: View Django usando mcp-fiscal-brasil.

Como o Django é síncrono por padrão, este exemplo usa as versões
síncronas do SDK (consultar_cnpj_sync, consultar_simples_sync) ou
asyncio.run() para adaptar corrotinas async.

Para Django 4.1+ com views async nativos, use as versões async diretamente.

Instalar dependências extras:
    pip install django

Configuração mínima no settings.py:
    INSTALLED_APPS = [...]
    ROOT_URLCONF = "myproject.urls"

Incluir em urls.py:
    from django.urls import path
    from . import django_integracao as views

    urlpatterns = [
        path("cnpj/<str:cnpj>/", views.consultar_cnpj),
        path("simples/<str:cnpj>/", views.consultar_simples),
        path("validar/cpf/<str:cpf>/", views.validar_cpf),
        path("nfe/status/<str:uf>/", views.status_sefaz),
    ]
"""

import asyncio
import json
import logging
from typing import Any

from mcp_fiscal_brasil import FiscalBrasil, validate_cnpj, validate_cpf

logger = logging.getLogger(__name__)

# Instância global reutilizada entre requests (sem recursos persistentes a fechar)
_fiscal = FiscalBrasil()


# ---------------------------------------------------------------------------
# Views sincronas (Django tradicional)
# ---------------------------------------------------------------------------


def consultar_cnpj(request: Any, cnpj: str) -> Any:
    """
    View Django síncrona para consultar CNPJ.

    URL: /cnpj/<cnpj>/
    Resposta: JSON com dados completos da empresa.
    """
    from django.http import JsonResponse  # type: ignore[import-not-found]

    if not validate_cnpj(cnpj):
        return JsonResponse({"erro": f"CNPJ inválido: {cnpj}"}, status=422)

    try:
        empresa = asyncio.run(_fiscal.consultar_cnpj(cnpj))
        return JsonResponse(empresa.model_dump(), json_dumps_params={"default": str})
    except Exception:
        logger.exception("Erro ao consultar CNPJ %s", cnpj)
        return JsonResponse({"erro": "Serviço temporariamente indisponível"}, status=503)


def consultar_simples(request: Any, cnpj: str) -> Any:
    """
    View Django síncrona para consultar Simples Nacional.

    URL: /simples/<cnpj>/
    """
    from django.http import JsonResponse  # type: ignore[import-not-found]

    if not validate_cnpj(cnpj):
        return JsonResponse({"erro": f"CNPJ inválido: {cnpj}"}, status=422)

    try:
        resultado = asyncio.run(_fiscal.consultar_simples(cnpj))
        return JsonResponse(resultado.model_dump(), json_dumps_params={"default": str})
    except Exception:
        logger.exception("Erro ao consultar Simples para CNPJ %s", cnpj)
        return JsonResponse({"erro": "Serviço temporariamente indisponível"}, status=503)


def validar_cpf(request: Any, cpf: str) -> Any:
    """
    View Django síncrona para validar CPF (offline).

    URL: /validar/cpf/<cpf>/
    """
    from django.http import JsonResponse  # type: ignore[import-not-found]

    return JsonResponse({"cpf": cpf, "valido": validate_cpf(cpf)})


def validar_cnpj_view(request: Any, cnpj: str) -> Any:
    """
    View Django síncrona para validar CNPJ (offline).

    URL: /validar/cnpj/<cnpj>/
    """
    from django.http import JsonResponse  # type: ignore[import-not-found]

    return JsonResponse({"cnpj": cnpj, "valido": validate_cnpj(cnpj)})


def status_sefaz(request: Any, uf: str) -> Any:
    """
    View Django síncrona para status do SEFAZ.

    URL: /nfe/status/<uf>/
    """
    from django.http import JsonResponse  # type: ignore[import-not-found]

    try:
        status = asyncio.run(_fiscal.status_sefaz(uf.upper()))
        return JsonResponse(status.model_dump(), json_dumps_params={"default": str})
    except Exception:
        logger.exception("Erro ao consultar status SEFAZ para UF %s", uf)
        return JsonResponse({"erro": "Serviço temporariamente indisponível"}, status=503)


# ---------------------------------------------------------------------------
# Views async nativas (Django 4.1+)
# ---------------------------------------------------------------------------


async def consultar_cnpj_async(request: Any, cnpj: str) -> Any:
    """
    View Django async para consultar CNPJ (Django 4.1+).

    Preferível ao wrapper síncrono em projetos Django com ASGI.
    """
    from django.http import JsonResponse  # type: ignore[import-not-found]

    if not validate_cnpj(cnpj):
        return JsonResponse({"erro": f"CNPJ inválido: {cnpj}"}, status=422)

    try:
        async with FiscalBrasil() as fiscal:
            empresa = await fiscal.consultar_cnpj(cnpj)
        return JsonResponse(empresa.model_dump(), json_dumps_params={"default": str})
    except Exception:
        logger.exception("Erro ao consultar CNPJ %s (async)", cnpj)
        return JsonResponse({"erro": "Serviço temporariamente indisponível"}, status=503)


# ---------------------------------------------------------------------------
# Exemplo de uso em management command Django
# ---------------------------------------------------------------------------


def exemplo_management_command() -> None:
    """
    Exemplo de uso em um management command Django (método handle).

    class Command(BaseCommand):
        def handle(self, *args, **options):
            exemplo_management_command()
    """
    cnpjs = ["33000167000101", "60746948000112"]

    async def processar() -> None:
        async with FiscalBrasil() as fiscal:
            for cnpj in cnpjs:
                try:
                    empresa = await fiscal.consultar_cnpj(cnpj)
                    simples = await fiscal.consultar_simples(cnpj)
                    dados = {
                        "cnpj": cnpj,
                        "razao_social": empresa.razao_social,
                        "simples": simples.optante_simples,
                        "mei": simples.optante_mei,
                    }
                    print(json.dumps(dados, ensure_ascii=False, default=str))
                except Exception as e:
                    print(f"Erro no CNPJ {cnpj}: {e}")

    asyncio.run(processar())
