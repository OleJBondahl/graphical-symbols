"""`scripts/fp_purity_gate.py` fails on I/O, clock, randomness and state writes in a pure module."""

import importlib.util
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parent.parent / "scripts" / "fp_purity_gate.py"
_spec = importlib.util.spec_from_file_location("fp_purity_gate", GATE)
assert _spec is not None
assert _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

PURE = "def f(x):\n    return x + 1\n"


def package(tmp_path, files):
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def reported(tmp_path, source):
    """Return the (line, what) pairs the gate reports for one pure module."""
    root = package(tmp_path, {"mod.py": source})
    return [(line, what) for _, line, what in gate.scan(root)]


def test_a_pure_module_is_not_reported(tmp_path):
    assert reported(tmp_path, PURE) == []


@pytest.mark.parametrize(
    ("source", "what"),
    [
        ("def f():\n    print('x')\n", "calls print()"),
        ("def f():\n    return input()\n", "calls input()"),
        ("def f():\n    return open('a')\n", "calls open()"),
        ("import time\n", "imports 'time'"),
        ("from datetime import datetime\n", "imports 'datetime'"),
        ("import random\n", "imports 'random'"),
        ("import os.path\n", "imports 'os'"),
        ("def f():\n    global X\n    X = 1\n", "`global` statement"),
        (
            "def f():\n    n = 0\n    def g():\n        nonlocal n\n    return g\n",
            "`nonlocal` statement",
        ),
        ("CACHE = {}\n\n\ndef f(k):\n    CACHE[k] = 1\n", "writes into module state 'CACHE'"),
        ("STATE = object()\n\n\ndef f():\n    STATE.x = 1\n", "writes into module state 'STATE'"),
        ("ITEMS = []\n\n\ndef f():\n    ITEMS.append(1)\n", "mutates module state 'ITEMS'"),
        ("ITEMS = {}\n\n\ndef f(k):\n    del ITEMS[k]\n", "writes into module state 'ITEMS'"),
    ],
)
def test_each_kind_of_impurity_is_reported(tmp_path, source, what):
    assert what in [w for _, w in reported(tmp_path, source)]


def test_the_report_names_the_line(tmp_path):
    assert reported(tmp_path, "X = 1\n\n\ndef f():\n    print(X)\n") == [(5, "calls print()")]


def test_local_names_and_relative_imports_are_fine(tmp_path):
    source = (
        "from . import sibling\n\n\ndef f(items):\n"
        "    out = []\n    out.append(items)\n    return out\n"
    )
    assert reported(tmp_path, source) == []


def test_impure_modules_are_skipped_by_path_relative_to_the_package(tmp_path):
    impure = "import os\n\nprint(os)\n"
    root = package(tmp_path, {"files.py": impure, "__init__.py": impure})
    assert gate.scan(root) == []


def test_subpackages_are_scanned_and_only_top_level_names_are_impure(tmp_path):
    impure = "import os\n"
    root = package(
        tmp_path,
        {
            "lint/__init__.py": impure,
            "lint/files.py": impure,
            "lint/ok.py": PURE,
            "files.py": impure,
        },
    )
    found = sorted(path.relative_to(root).as_posix() for path, _, _ in gate.scan(root))
    assert found == ["lint/__init__.py", "lint/files.py"]


def test_main_passes_on_the_real_tree(capsys):
    assert gate.main() == 0
    assert "free of I/O, clock, randomness and state" in capsys.readouterr().out


def test_main_fails_on_a_tree_with_a_print(tmp_path, monkeypatch, capsys):
    package(tmp_path, {"src/symdef/mod.py": "def f():\n    print('x')\n"})
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "PACKAGE_DIR", tmp_path / "src" / "symdef")

    assert gate.main() == 1

    out = capsys.readouterr().out
    assert "1 violation(s)" in out
    assert "src/symdef/mod.py:2 calls print()" in out


def test_main_fails_when_the_package_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "PACKAGE_DIR", tmp_path / "nowhere")

    assert gate.main() == 2
    assert "not found" in capsys.readouterr().err


def test_no_file_imports_deal_and_the_project_lists_it_nowhere():
    root = GATE.parent.parent
    for folder in ("src", "scripts", "tests"):
        for py in (root / folder).rglob("*.py"):
            if py != Path(__file__):
                assert "import deal" not in py.read_text(encoding="utf-8"), py
    assert "deal" not in (root / "pyproject.toml").read_text(encoding="utf-8")
