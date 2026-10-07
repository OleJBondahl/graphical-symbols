"""The newcomer's path: `init`, `build` and `check`, as functions and as the command (D48)."""

import runpy
import sys

import pytest

import symdef
from symdef.cli import main
from symdef.errors import LibraryError

SYMBOL = "symbols/resistor.toml"


def run(*argv):
    return main([str(a) for a in argv])


@pytest.fixture
def built(tmp_path):
    assert run("init", tmp_path) == 0
    assert run("build", tmp_path) == 0
    return tmp_path


def edit(root, relative, old, new):
    path = root / relative
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def rules(findings):
    return {f.rule for f in findings}


class TestTheThreeVerbsInAnEmptyFolder:
    def test_all_three_exit_zero(self, tmp_path, capsys):
        assert [run(v, tmp_path) for v in ("init", "build", "check")] == [0, 0, 0]
        assert "library.toml" in capsys.readouterr().out

    def test_the_python_functions_do_the_same(self, tmp_path):
        assert len(symdef.init(tmp_path)) == 3
        assert len(symdef.build(tmp_path)) == 5
        assert symdef.check(tmp_path) == ()

    def test_init_writes_lf_line_ends_and_the_schema_line(self, tmp_path):
        symdef.init(tmp_path)
        assert (tmp_path / ".gitattributes").read_bytes() == b"* text=auto eol=lf\n"
        assert (tmp_path / "library.toml").read_text().startswith("#:schema https://")
        assert b"\r" not in (tmp_path / SYMBOL).read_bytes()

    def test_init_refuses_a_folder_that_has_a_set_and_writes_nothing(self, tmp_path, capsys):
        (tmp_path / "library.toml").write_text("", encoding="utf-8")
        assert run("init", tmp_path) == 1
        assert not (tmp_path / "symbols").exists()
        assert "exists" in capsys.readouterr().err

    def test_python_dash_m_runs_the_command(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["symdef", "init", str(tmp_path)])
        with pytest.raises(SystemExit) as stop:
            runpy.run_module("symdef", run_name="__main__")
        assert stop.value.code == 0
        assert (tmp_path / "library.toml").is_file()

    def test_a_bad_verb_is_a_usage_error(self, tmp_path):
        with pytest.raises(SystemExit) as stop:
            run("explode", tmp_path)
        assert stop.value.code == 2


class TestBuild:
    def test_a_broken_symbol_fails_and_writes_nothing(self, tmp_path, capsys):
        symdef.init(tmp_path)
        edit(tmp_path, SYMBOL, "[0, -2], dir", "[0, -1.5], dir")
        assert run("build", tmp_path) == 1
        assert "port-off-wiring-grid" in capsys.readouterr().out
        assert not (tmp_path / "build").exists()

    def test_the_python_function_raises_with_the_findings(self, tmp_path):
        symdef.init(tmp_path)
        edit(tmp_path, SYMBOL, "[0, -2], dir", "[0, -1.5], dir")
        with pytest.raises(LibraryError) as raised:
            symdef.build(tmp_path)
        assert "port-off-wiring-grid" in rules(raised.value.findings)


class TestCheck:
    def test_a_stale_build_fails(self, built, capsys):
        edit(built, SYMBOL, 'name = "Resistor"', 'name = "Resistor 2"')
        assert run("check", built) == 1
        assert "stale-build" in capsys.readouterr().out
        assert "stale-build" in rules(symdef.check(built))

    def test_a_missing_bundle_is_stale_not_a_crash(self, built):
        (built / "src" / "mysymbols" / "bundle.json").unlink()
        assert rules(symdef.check(built)) == {"stale-build"}

    def test_a_symbol_that_does_not_lint_fails(self, built):
        edit(built, SYMBOL, "[0, -2], dir", "[0, -1.5], dir")
        assert "port-off-wiring-grid" in rules(symdef.check(built))

    def test_a_file_that_does_not_load_returns_its_findings(self, built):
        edit(built, SYMBOL, 'kind = "impedance"', 'kind = "pipe"')
        assert "schema" in rules(symdef.check(built))

    def test_a_symbol_that_fails_only_when_repeated(self, built):
        # Wider than the default pole pitch of 4: fine alone, overflowing when repeated (gate 3).
        edit(
            built,
            SYMBOL,
            "[-0.5, -1], [0.5, -1], [0.5, 1], [-0.5, 1]",
            "[-3, -1], [3, -1], [3, 1], [-3, 1]",
        )
        edit(built, SYMBOL, "at = [0.75, -1.5]", "at = [3.25, -1.5]")
        edit(built, SYMBOL, "at = [0.75, 1.5]", "at = [3.25, 1.5]")
        found = symdef.check(built)
        assert any("repeated 3 times" in f.message for f in found)

    def test_a_corrupt_bundle_is_reported(self, built):
        (built / "src" / "mysymbols" / "bundle.json").write_text("{", encoding="utf-8")
        assert "schema" in rules(symdef.check(built))

    def test_a_bundle_that_differs_from_the_source_is_reported(self, built):
        path = built / "src" / "mysymbols" / "bundle.json"
        path.write_text(path.read_text(encoding="utf-8").replace('"Resistor"', '"Resister"'))
        found = symdef.check(built)
        assert {"bundle-differs", "stale-build"} <= rules(found)

    def test_a_bundle_with_other_numbers_is_reported(self, built):
        (built / SYMBOL).rename(built / "symbols" / "other.toml")
        edit(built, "symbols/other.toml", 'number = "resistor"', 'number = "other"')
        found = symdef.check(built)
        assert any(f.rule == "bundle-differs" and "numbers" in f.message for f in found)
