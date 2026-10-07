"""Every name the docs tell a user to import is in `__all__` of its module (D47)."""

import ast
import importlib
import json
from importlib.resources import files
from pathlib import Path

import pytest
from test_readme import BLOCK, GUIDE, README

import symdef

DOCS = [README, GUIDE]


def imported_names(path: Path) -> list[tuple[str, str]]:
    """Return (module, name) for each `from symdef... import name` in a file's python blocks."""
    found = []
    for code in BLOCK.findall(path.read_text(encoding="utf-8")):
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "symdef":
                found.extend((node.module or "", alias.name) for alias in node.names)
    return found


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_documented_imports_are_in_all(path):
    names = imported_names(path)
    assert names
    missing = [(m, n) for m, n in names if n not in importlib.import_module(m).__all__]
    assert missing == []


def test_the_two_names_the_spec_names_are_public():
    assert {"RULES", "finding_key"} <= set(symdef.__all__)
    assert {"RULES", "finding_key"} <= set(importlib.import_module("symdef.lint").__all__)


def test_the_schema_is_package_data_with_an_id_on_the_pages_site():
    text = files("symdef").joinpath("schema", "symbol.schema.json").read_text(encoding="utf-8")
    assert json.loads(text)["$id"] == "https://olejbondahl.github.io/symdef/symbol.schema.json"
