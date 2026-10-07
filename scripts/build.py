"""Write `src/symdef/_version.py` from the version in `pyproject.toml`.

The package version is then a constant the layout reads without asking package metadata. Run
it after changing `version`; `tests/test_version.py` fails while the two disagree.

Usage:
    uv run python scripts/build.py
"""

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
VERSION_MODULE = ROOT / "src" / "symdef" / "_version.py"


def project_version(pyproject_text: str) -> str:
    """Return `[project].version` of a `pyproject.toml`'s text."""
    return tomllib.loads(pyproject_text)["project"]["version"]


def version_module(version: str) -> str:
    """Return the text of `_version.py` for `version`."""
    return (
        '"""The package version, written by scripts/build.py. Do not edit."""\n'
        "\n"
        f'LIBRARY_VERSION = "{version}"\n'
    )


def main() -> None:
    """Write `_version.py` from the version in `pyproject.toml`."""
    version = project_version(PYPROJECT.read_text(encoding="utf-8"))
    VERSION_MODULE.write_text(version_module(version), encoding="utf-8", newline="\n")
    sys.stdout.write(f"build: {VERSION_MODULE.name} written for version {version}\n")


if __name__ == "__main__":
    main()
