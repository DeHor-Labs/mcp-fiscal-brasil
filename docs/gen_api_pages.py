"""Gera paginas de referencia de API automaticamente a partir do codigo Python.

Executado pelo plugin `mkdocs-gen-files` em cada build do site. Para cada
modulo em `src/mcp_fiscal_brasil/`, cria uma pagina em `reference/<modulo>.md`
contendo `:::mcp_fiscal_brasil.<modulo>` que o mkdocstrings expande para
documentacao gerada das docstrings.

Sem este script, cada modulo precisaria de pagina escrita a mao. Com ele,
basta escrever boas docstrings nos `.py` e a doc fica em sincronia automatica.
"""

from __future__ import annotations

import re
from pathlib import Path

import mkdocs_gen_files

SRC = Path("src/mcp_fiscal_brasil")
REFERENCE_ROOT = Path("reference")

# Modulos a documentar (caminhos relativos a src/mcp_fiscal_brasil/)
MODULES_TO_DOCUMENT = [
    "_core",
    "agentic",
    "cnpj",
    "cpf",
    "cep",
    "nfe",
    "nfse",
    "sped",
    "esocial",
    "simples",
    "mei",
    "cnae",
    "ibge",
    "empresa",
    "certidoes",
    "shared",
    "sdk",
    "cli",
    "api",
    "server",
]


def _module_title(name: str) -> str:
    if name == "_core":
        return "Infraestrutura comum (`_core`)"
    if name == "agentic":
        return "Tools agenticas (`agentic`)"
    if name == "sdk":
        return "SDK Python"
    if name == "cli":
        return "CLI"
    if name == "api":
        return "REST API"
    if name == "server":
        return "Servidor MCP"
    return f"`{name}`"


nav = mkdocs_gen_files.Nav()


for module in MODULES_TO_DOCUMENT:
    module_path = SRC / module
    if module_path.is_dir():
        doc_path = REFERENCE_ROOT / module / "index.md"
        identifier = f"mcp_fiscal_brasil.{module}"
    elif (SRC / f"{module}.py").is_file():
        doc_path = REFERENCE_ROOT / f"{module}.md"
        identifier = f"mcp_fiscal_brasil.{module}"
    else:
        continue

    with mkdocs_gen_files.open(doc_path, "w") as fd:
        fd.write(f"# {_module_title(module)}\n\n")
        fd.write(f"::: {identifier}\n")
        fd.write("    options:\n")
        fd.write("      show_source: false\n")
        fd.write("      show_root_heading: false\n")
        fd.write("      show_submodules: true\n")
        fd.write("      members_order: source\n")
        fd.write("      docstring_style: google\n")
        fd.write("      separate_signature: true\n")
        fd.write("      filters:\n")
        fd.write("        - '!^_'\n")  # esconde _privates
        fd.write("      heading_level: 2\n")

    nav[(module,)] = f"{module}/index.md" if module_path.is_dir() else f"{module}.md"


with mkdocs_gen_files.open(REFERENCE_ROOT / "SUMMARY.md", "w") as fd:
    fd.writelines(nav.build_literate_nav())


# O MkDocs transforma docs/index.md em HTML. Esta cópia mantém a representação
# Markdown disponível como arquivo real, sem cair no HTML da aplicação. Os links
# relativos apontam para as rotas HTML geradas, não para fontes .md ausentes.
RAW_INDEX_TARGET = Path("site/index.md")
RAW_INDEX_TARGET.parent.mkdir(parents=True, exist_ok=True)


def _published_markdown_link(match: re.Match[str]) -> str:
    target = match.group("target")
    if target in {"index.md", "./index.md"}:
        target = "./"
    elif target.endswith("/index.md"):
        target = target[: -len("index.md")]
    else:
        target = target[:-3] + "/"
    return f"]({target}{match.group('fragment') or ''})"


raw_index = Path("docs/index.md").read_text(encoding="utf-8")
raw_index = re.sub(
    r"]\((?P<target>(?![A-Za-z][A-Za-z0-9+.-]*:|/|#)[^)#\s]+\.md)(?P<fragment>#[^)\s]+)?\)",
    _published_markdown_link,
    raw_index,
)
RAW_INDEX_TARGET.write_text(raw_index, encoding="utf-8")
