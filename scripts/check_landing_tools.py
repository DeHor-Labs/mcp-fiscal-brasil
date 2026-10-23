"""Confere se a landing page lista exatamente as tools registradas no servidor MCP."""

from __future__ import annotations

import asyncio
import pathlib
import re
import sys

from mcp_fiscal_brasil.server import app

LANDING = pathlib.Path(__file__).resolve().parents[1] / "landing"
TOOL = re.compile(r'<code class="tool">(\w+)</code>')


def main() -> int:
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    og = (LANDING / "_og" / "og.html").read_text(encoding="utf-8")
    registradas = {t.name for t in asyncio.run(app.list_tools())}
    total = str(len(registradas))
    na_pagina = TOOL.findall(html)
    erros = []

    if set(na_pagina) != registradas or len(na_pagina) != len(set(na_pagina)):
        erros.append(f"faltando na página: {sorted(registradas - set(na_pagina))}")
        erros.append(f"inexistentes no servidor: {sorted(set(na_pagina) - registradas)}")
        erros.append(f"repetidas: {sorted({t for t in na_pagina if na_pagina.count(t) > 1})}")

    citados = set(re.findall(r"\b(\d+) ferramentas", html))
    if citados != {total}:
        erros.append(f"contagens citadas na página {sorted(citados)} != {total}")

    if f"<b>{total}</b> ferramentas" not in og:
        erros.append(f"landing/_og/og.html não cita {total} ferramentas")

    for card in html.split('<div class="card">'):
        cabecalho = re.search(r"<h3>(.*?) <small>(\d+)</small></h3>", card)
        if cabecalho:
            nome, declarado = cabecalho.groups()
            listadas = len(TOOL.findall(card))
            if int(declarado) != listadas:
                erros.append(f"categoria {nome!r}: declara {declarado}, lista {listadas}")

    for e in erros:
        print(f"FALHA: {e}")
    if not erros:
        print(f"OK: {total} tools na landing, na imagem OG e no servidor; categorias conferem.")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
