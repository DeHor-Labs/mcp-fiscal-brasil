"""Testes para configuracao de logging estruturado."""

from mcp_fiscal_brasil._core import get_logger


def test_get_logger_respeita_mcp_fiscal_log_level(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MCP_FISCAL_LOG_LEVEL", "ERROR")

    logger = get_logger("tests.logging")
    logger.info("evento_oculto")
    logger.error("evento_visivel")

    captured = capsys.readouterr()
    assert "evento_visivel" in captured.err
    assert "evento_oculto" not in captured.err


def test_get_logger_log_level_invalido_cai_para_info(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MCP_FISCAL_LOG_LEVEL", "NIVEL_INEXISTENTE")

    logger = get_logger("tests.logging")
    logger.info("evento_info")

    captured = capsys.readouterr()
    assert "evento_info" in captured.err
