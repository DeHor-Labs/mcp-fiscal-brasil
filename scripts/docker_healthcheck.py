#!/usr/bin/env python3
"""Healthcheck do container Docker do mcp-fiscal-brasil.

O CMD padrao da imagem roda o servidor MCP via stdio (sem porta HTTP), mas o
mesmo container tambem pode ser usado para a REST API (`mcp-fiscal-api`) ou o
transporte MCP HTTP. Um HEALTHCHECK fixo em HTTP falharia sempre no modo
stdio; um HEALTHCHECK fixo em import nao detectaria a API travada.

Este script degrada automaticamente: se a porta configurada estiver
escutando, valida via HTTP GET /health; caso contrario, confirma apenas que o
pacote importa (suficiente para o modo stdio, que nao abre porta).

Exit 0 = saudavel, exit 1 = nao saudavel.
"""

from __future__ import annotations

import os
import socket
import sys
import urllib.request

PORT = int(os.environ.get("PORT", "8000"))
_TIMEOUT_SECONDS = 3.0


def _porta_aberta() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def main() -> int:
    if _porta_aberta():
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/health", timeout=_TIMEOUT_SECONDS
            ) as resp:
                return 0 if resp.status == 200 else 1
        except Exception as exc:
            print(f"Erro no healthcheck HTTP: {exc}", file=sys.stderr)
            return 1

    try:
        import mcp_fiscal_brasil  # noqa: F401
    except Exception as exc:
        print(f"Erro no import do pacote: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
