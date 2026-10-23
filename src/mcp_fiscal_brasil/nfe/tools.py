"""MCP tools for NFe lookups and validation."""

from mcp_fiscal_brasil._core import FiscalValidationError, get_logger

from ..shared.exceptions import ValidationError
from ..shared.validators import validate_chave_nfe
from .client import NFEClient
from .schemas import NFeResponse, StatusSEFAZResponse

logger = get_logger(__name__)

_client = NFEClient()


class NFeValidationError(FiscalValidationError, ValidationError):
    """Validation error compatible with both core and legacy exception hierarchies."""

    def __init__(self, field: str, value: str, reason: str) -> None:
        ValidationError.__init__(self, field=field, value=value, reason=reason)
        self.detail = dict(self.details)


# Valid state abbreviations for SEFAZ lookup.
UFS_VALIDAS = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}


async def consultar_nfe(chave_acesso: str) -> NFeResponse:
    """
    Look up NFe (Nota Fiscal Eletrônica) data by access key.

    The access key has 44 digits and is printed on the DANFE document.

    Args:
        chave_acesso: 44 digit NFe access key, accepted with or without spaces.

    Returns:
        NFeResponse with issuer, recipient, items and totals.

    Raises:
        FiscalValidationError: If the access key is invalid.
        FiscalNotFoundError: If the NFe is not found.
        FiscalHTTPError: If SEFAZ or an upstream API fails.
    """
    chave_limpa = "".join(c for c in chave_acesso if c.isdigit())

    if not validate_chave_nfe(chave_limpa):
        raise NFeValidationError(
            field="chave_acesso",
            value=chave_acesso,
            reason=(
                "Chave de acesso NFe inválida. Deve ter 44 dígitos com dígito verificador correto."
            ),
        )

    return await _client.consultar_por_chave(chave_limpa)


async def consultar_nfce(chave_acesso: str) -> NFeResponse:
    """
    Look up NFC-e (Nota Fiscal de Consumidor Eletronica, modelo 65) data by access key.

    A NFC-e e a nota do varejo ao consumidor final. A cobertura completa depende do
    provedor premium opcional cpfcnpj.com.br (pacote 102), habilitado por token.

    Args:
        chave_acesso: 44 digit NFC-e access key, accepted with or without spaces.

    Returns:
        NFeResponse with issuer, recipient and totals (layout compartilhado com a NF-e).

    Raises:
        FiscalValidationError: If the access key is invalid.
        FiscalHTTPError: If the upstream provider fails.
    """
    chave_limpa = "".join(c for c in chave_acesso if c.isdigit())

    if not validate_chave_nfe(chave_limpa):
        raise NFeValidationError(
            field="chave_acesso",
            value=chave_acesso,
            reason=(
                "Chave de acesso NFC-e inválida. "
                "Deve ter 44 dígitos com dígito verificador correto."
            ),
        )

    # As posicoes 21-22 da chave (indice 20:22) carregam o modelo do documento.
    # A NFC-e e o modelo 65; uma chave de modelo 55 (NF-e) passa na validacao de
    # digito verificador, mas nao deve ser consultada aqui, senao o provedor
    # escolheria o pacote 100 e devolveria uma NF-e onde se prometeu NFC-e.
    modelo = chave_limpa[20:22]
    if modelo != "65":
        raise NFeValidationError(
            field="chave_acesso",
            value=chave_acesso,
            reason=(
                f"Chave de modelo {modelo}, esperado modelo 65 (NFC-e). "
                "Para NF-e (modelo 55) use consultar_nfe."
            ),
        )

    return await _client.consultar_por_chave(chave_limpa)


async def validar_chave_nfe(chave_acesso: str) -> dict[str, object]:
    """
    Validate the format and check digit of an NFe access key.

    This does not call external APIs. It only verifies the modulo 11 check digit.

    Args:
        chave_acesso: 44 digit access key.

    Returns:
        Dictionary with validity and decoded fields when valid.
    """
    chave_limpa = "".join(c for c in chave_acesso if c.isdigit())
    válido = validate_chave_nfe(chave_limpa)

    resultado: dict[str, object] = {
        "válido": válido,
        "chave_formatada": " ".join(chave_limpa[i : i + 4] for i in range(0, 44, 4))
        if len(chave_limpa) == 44
        else None,
    }

    if válido and len(chave_limpa) == 44:
        from ..shared.constants import CODIGO_UF

        cod_uf = int(chave_limpa[:2])
        resultado.update(
            {
                "uf": CODIGO_UF.get(cod_uf, f"UF {cod_uf}"),
                "ano_mes_emissao": f"{chave_limpa[4:6]}/{chave_limpa[2:4]}",
                "cnpj_emitente": chave_limpa[6:20],
                "modelo": chave_limpa[20:22],
                "serie": chave_limpa[22:25],
                "número": chave_limpa[25:34],
            }
        )

    return resultado


async def consultar_status_sefaz(uf: str) -> StatusSEFAZResponse:
    """
    Look up the current SEFAZ service status for a state.

    Checks whether the SEFAZ NFe issuance webservice is operational.

    Args:
        uf: State abbreviation, for example 'SP', 'MG' or 'RJ'.

    Returns:
        StatusSEFAZResponse with current status and description.

    Raises:
        FiscalValidationError: If the state abbreviation is invalid.
    """
    uf_upper = uf.upper().strip()
    if uf_upper not in UFS_VALIDAS:
        raise NFeValidationError(
            field="uf",
            value=uf,
            reason=f"UF inválida. Use uma das siglas: {', '.join(sorted(UFS_VALIDAS))}",
        )

    return await _client.consultar_status_servico(uf_upper)
