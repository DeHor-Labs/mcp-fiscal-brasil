"""Testes para nfse/schemas.py (NFSeResponse)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mcp_fiscal_brasil.nfse.schemas import NFSeResponse

# ---------------------------------------------------------------------------
# Instanciacao basica
# ---------------------------------------------------------------------------


def test_instancia_com_campos_obrigatorios():
    nfse = NFSeResponse(numero="001", municipio="São Paulo", uf="SP")
    assert nfse.numero == "001"
    assert nfse.municipio == "São Paulo"
    assert nfse.uf == "SP"
    assert nfse.sucesso is True


def test_instancia_com_todos_os_campos():
    ts = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    nfse = NFSeResponse(
        numero="00123",
        municipio="Goiânia",
        uf="GO",
        prestador_cnpj="12345678000195",
        prestador_razao_social="Empresa Prestadora Ltda",
        tomador_cnpj_cpf="98765432000100",
        tomador_razao_social="Tomador S.A.",
        data_emissao=ts,
        descricao_servico="Consultoria em sistemas fiscais",
        valor_servico=1500.00,
        valor_iss=75.00,
        aliquota_iss=5.0,
        codigo_municipio_servico="5208707",
        codigo_cnae="6201500",
        situacao="ATIVA",
        observacoes="NFS-e emitida conforme legislacao municipal",
    )
    assert nfse.numero == "00123"
    assert nfse.municipio == "Goiânia"
    assert nfse.uf == "GO"
    assert nfse.prestador_cnpj == "12345678000195"
    assert nfse.prestador_razao_social == "Empresa Prestadora Ltda"
    assert nfse.tomador_cnpj_cpf == "98765432000100"
    assert nfse.tomador_razao_social == "Tomador S.A."
    assert nfse.data_emissao == ts
    assert nfse.descricao_servico == "Consultoria em sistemas fiscais"
    assert nfse.valor_servico == 1500.00
    assert nfse.valor_iss == 75.00
    assert nfse.aliquota_iss == 5.0
    assert nfse.codigo_municipio_servico == "5208707"
    assert nfse.codigo_cnae == "6201500"
    assert nfse.situacao == "ATIVA"
    assert nfse.observacoes == "NFS-e emitida conforme legislacao municipal"


# ---------------------------------------------------------------------------
# Campos opcionais sao None por padrao
# ---------------------------------------------------------------------------


def test_campos_opcionais_sao_none_por_padrao():
    nfse = NFSeResponse(numero="002", municipio="Campinas", uf="SP")
    assert nfse.prestador_cnpj is None
    assert nfse.prestador_razao_social is None
    assert nfse.tomador_cnpj_cpf is None
    assert nfse.tomador_razao_social is None
    assert nfse.data_emissao is None
    assert nfse.descricao_servico is None
    assert nfse.valor_servico is None
    assert nfse.valor_iss is None
    assert nfse.aliquota_iss is None
    assert nfse.codigo_municipio_servico is None
    assert nfse.codigo_cnae is None
    assert nfse.situacao is None
    assert nfse.observacoes is None


# ---------------------------------------------------------------------------
# Heranca de BaseResponse
# ---------------------------------------------------------------------------


def test_herda_sucesso_true():
    nfse = NFSeResponse(numero="003", municipio="Curitiba", uf="PR")
    assert nfse.sucesso is True


def test_herda_consultado_em_preenchido_automaticamente():
    nfse = NFSeResponse(numero="004", municipio="Fortaleza", uf="CE")
    assert nfse.consultado_em is not None
    assert isinstance(nfse.consultado_em, datetime)


def test_sucesso_pode_ser_sobrescrito():
    nfse = NFSeResponse(numero="005", municipio="Salvador", uf="BA", sucesso=False)
    assert nfse.sucesso is False


# ---------------------------------------------------------------------------
# Campos obrigatorios ausentes levantam ValidationError
# ---------------------------------------------------------------------------


def test_sem_numero_levanta_erro():
    with pytest.raises(ValidationError) as exc_info:
        NFSeResponse(municipio="Brasília", uf="DF")  # type: ignore[call-arg]
    assert "numero" in str(exc_info.value)


def test_sem_municipio_levanta_erro():
    with pytest.raises(ValidationError) as exc_info:
        NFSeResponse(numero="001", uf="MG")  # type: ignore[call-arg]
    assert "municipio" in str(exc_info.value)


def test_sem_uf_levanta_erro():
    with pytest.raises(ValidationError) as exc_info:
        NFSeResponse(numero="001", municipio="Belo Horizonte")  # type: ignore[call-arg]
    assert "uf" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Serializacao (model_dump / model_dump_json)
# ---------------------------------------------------------------------------


def test_model_dump_inclui_campos_obrigatorios():
    nfse = NFSeResponse(numero="010", municipio="Manaus", uf="AM")
    data = nfse.model_dump()
    assert data["numero"] == "010"
    assert data["municipio"] == "Manaus"
    assert data["uf"] == "AM"
    assert data["sucesso"] is True
    assert "consultado_em" in data


def test_model_dump_exclui_none_com_exclude_none():
    nfse = NFSeResponse(numero="011", municipio="Natal", uf="RN")
    data = nfse.model_dump(exclude_none=True)
    # Campos None nao devem aparecer quando exclude_none=True
    assert "prestador_cnpj" not in data
    assert "valor_servico" not in data


def test_model_dump_inclui_none_por_padrao():
    nfse = NFSeResponse(numero="012", municipio="Maceio", uf="AL")
    data = nfse.model_dump()
    assert "prestador_cnpj" in data
    assert data["prestador_cnpj"] is None


def test_model_dump_json_serializavel():
    import json

    ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    nfse = NFSeResponse(
        numero="013",
        municipio="Porto Alegre",
        uf="RS",
        data_emissao=ts,
        valor_servico=500.0,
    )
    json_str = nfse.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["numero"] == "013"
    assert parsed["valor_servico"] == 500.0


# ---------------------------------------------------------------------------
# Tipos dos campos
# ---------------------------------------------------------------------------


def test_valor_servico_aceita_float():
    nfse = NFSeResponse(numero="020", municipio="Recife", uf="PE", valor_servico=1234.56)
    assert nfse.valor_servico == 1234.56


def test_valor_iss_aceita_float():
    nfse = NFSeResponse(numero="021", municipio="João Pessoa", uf="PB", valor_iss=61.73)
    assert nfse.valor_iss == 61.73


def test_aliquota_iss_aceita_float():
    nfse = NFSeResponse(numero="022", municipio="Teresina", uf="PI", aliquota_iss=2.5)
    assert nfse.aliquota_iss == 2.5


def test_data_emissao_aceita_datetime():
    ts = datetime(2025, 1, 10, 8, 0, tzinfo=timezone.utc)
    nfse = NFSeResponse(numero="023", municipio="Belém", uf="PA", data_emissao=ts)
    assert nfse.data_emissao == ts


def test_data_emissao_aceita_string_iso():
    nfse = NFSeResponse(
        numero="024",
        municipio="Macapá",
        uf="AP",
        data_emissao="2025-06-15T14:00:00Z",  # type: ignore[arg-type]
    )
    assert isinstance(nfse.data_emissao, datetime)


# ---------------------------------------------------------------------------
# Igualdade e representacao
# ---------------------------------------------------------------------------


def test_instancias_iguais_com_mesmos_dados():
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    nfse1 = NFSeResponse(numero="030", municipio="Vitória", uf="ES", consultado_em=ts)
    nfse2 = NFSeResponse(numero="030", municipio="Vitória", uf="ES", consultado_em=ts)
    assert nfse1 == nfse2


def test_instancias_diferentes_com_dados_diferentes():
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    nfse1 = NFSeResponse(numero="031", municipio="Florianópolis", uf="SC", consultado_em=ts)
    nfse2 = NFSeResponse(numero="032", municipio="Florianópolis", uf="SC", consultado_em=ts)
    assert nfse1 != nfse2
