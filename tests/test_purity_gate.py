import importlib.util
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / "scripts" / "fp_purity_gate.py"
_spec = importlib.util.spec_from_file_location("fp_purity_gate", GATE)
assert _spec is not None
assert _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

UNDECORATED = "def f():\n    return 1\n"
DECORATED = "import deal\n\n\n@deal.pure\ndef f():\n    return 1\n"


def package(tmp_path, files):
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def names(missing, root):
    return sorted((path.relative_to(root).as_posix(), name) for path, _, name in missing)


def test_undecorated_function_is_reported(tmp_path):
    root = package(tmp_path, {"mod.py": UNDECORATED})
    assert names(gate.scan(root), root) == [("mod.py", "f")]


def test_reported_with_its_line_number(tmp_path):
    root = package(tmp_path, {"mod.py": "X = 1\n\n\n" + UNDECORATED})
    ((_, lineno, _),) = gate.scan(root)
    assert lineno == 4


def test_decorated_function_is_not_reported(tmp_path):
    root = package(tmp_path, {"mod.py": DECORATED})
    assert gate.scan(root) == []


def test_impure_modules_are_skipped_by_path_relative_to_the_package(tmp_path):
    root = package(tmp_path, {"build.py": UNDECORATED, "__init__.py": UNDECORATED})
    assert gate.scan(root) == []


def test_subpackages_are_scanned_and_only_top_level_names_are_impure(tmp_path):
    root = package(
        tmp_path,
        {
            "lint/__init__.py": UNDECORATED,
            "lint/rules.py": UNDECORATED,
            "lint/build.py": UNDECORATED,
            "lint/ok.py": DECORATED,
        },
    )
    assert names(gate.scan(root), root) == [
        ("lint/__init__.py", "f"),
        ("lint/build.py", "f"),
        ("lint/rules.py", "f"),
    ]


def test_methods_are_not_module_level(tmp_path):
    source = "class C:\n    def m(self):\n        return 1\n"
    root = package(tmp_path, {"mod.py": source})
    assert gate.scan(root) == []


def test_main_passes_on_the_real_tree(capsys):
    assert gate.main() == 0
    assert "every module-level function in pure modules has @deal.pure" in capsys.readouterr().out


def test_main_fails_on_a_tree_with_an_undecorated_function(tmp_path, monkeypatch, capsys):
    package(tmp_path, {"src/symdef/mod.py": UNDECORATED})
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "PACKAGE_DIR", tmp_path / "src" / "symdef")

    assert gate.main() == 1

    out = capsys.readouterr().out
    assert "1 function(s) missing @deal.pure" in out
    assert "src/symdef/mod.py:1 f" in out


def test_main_fails_when_the_package_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "PACKAGE_DIR", tmp_path / "nowhere")

    assert gate.main() == 2
    assert "not found" in capsys.readouterr().err
