from __future__ import annotations

import json
import pathlib
import sys

try:
    import tomllib  # py311+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[import-not-found]


def main() -> int:
    root = pathlib.Path.cwd()

    with (root / "pyproject.toml").open("rb") as fp:
        project_data = tomllib.load(fp)

    with (root / "server.json").open("r", encoding="utf-8") as fp:
        server_data = json.load(fp)

    with (root / "npm-wrapper" / "package.json").open("r", encoding="utf-8") as fp:
        npm_data = json.load(fp)

    with (root / "CHANGELOG.md").open("r", encoding="utf-8") as fp:
        changelog = fp.read()

    versions = {
        "pyproject.toml": project_data["project"]["version"],
        "server.json": server_data["version"],
        "npm-wrapper/package.json": npm_data["version"],
    }

    unique_versions = set(versions.values())
    release_version = project_data["project"]["version"]

    if len(unique_versions) != 1:
        print("FALHA: versões inconsistentes nos metadados.")
        for file_path, version in versions.items():
            print(f"  {file_path}: {version}")
        return 1

    if f"## [{release_version}]" not in changelog:
        print(f"FALHA: seção ## [{release_version}] não encontrada no CHANGELOG.md.")
        return 1

    print(f"OK: release metadata consistente ({release_version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
