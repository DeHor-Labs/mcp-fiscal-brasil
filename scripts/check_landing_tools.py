"""Confere se a landing page lista exatamente as tools registradas no servidor MCP."""

from __future__ import annotations

import asyncio
import pathlib
import re
import sys

from mcp_fiscal_brasil.server import app


def main() -> int:
    html = (pathlib.Path(__file__).resolve().parents[1] / "landing" / "index.html").read_text()
    na_pagina = set(re.findall(r'<code class="tool">(\w+)</code>', html))
    registradas = {t.name for t in asyncio.run(app.list_tools())}
    total = len(registradas)
    citados = set(re.findall(r"\b(\d+) ferramentas", html))
    erros = []
    if na_pagina != registradas:
        erros.append(f"faltando na página: {sorted(registradas - na_pagina)}")
        erros.append(f"inexistentes no servidor: {sorted(na_pagina - registradas)}")
    if citados != {str(total)}:
        erros.append(f"contagens citadas {sorted(citados)} != {total} registradas")
    for e in erros:
        print(f"FALHA: {e}")
    if not erros:
        print(f"OK: {total} tools na landing e no servidor.")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
