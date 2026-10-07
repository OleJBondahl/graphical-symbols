"""The tutorial set at docs/tutorial-set loads, lints clean and keeps the guide files."""

import shutil
from pathlib import Path

import pytest

import symdef

ROOT = Path(__file__).resolve().parent.parent
SET = ROOT / "docs" / "tutorial-set"
GUIDE = ROOT / "tests" / "fixtures" / "guide" / "symbols"
IEC = ("S00016", "S00171", "S00227", "S00230", "S00254", "S00305")
NEW = ("S90001", "S90002", "S90003")


def test_the_set_is_source_only():
    assert sorted(p.name for p in SET.iterdir()) == ["library.toml", "symbols"]


def test_it_builds_and_checks_clean_on_a_throwaway_copy(tmp_path):
    """The set itself stays source-only, so the build goes into a copy."""
    copy = tmp_path / "set"
    shutil.copytree(SET, copy)
    symdef.build(copy)
    assert symdef.check(copy) == ()


def test_the_nine_numbers_are_exactly_the_expected_list():
    assert sorted(symdef.load_library(SET).symbols) == sorted(IEC + NEW)


@pytest.mark.parametrize("number", IEC)
def test_each_iec_file_equals_the_guide_fixture(number):
    ours = (SET / "symbols" / f"{number}.toml").read_bytes()
    theirs = (GUIDE / f"{number}.toml").read_bytes()
    if number == "S00254":
        # The one edit: the fixture's own concern C1 (pitch-overflow) says pole_pitch = 8.
        theirs = theirs.replace(b"\n\nparts", b"\npole_pitch = 8\n\nparts", 1)
    assert ours == theirs


def test_the_new_symbols_use_the_sets_own_pipe_word():
    library = symdef.load_library(SET)
    assert "pipe" in library.vocabulary.path_kinds
    for number in NEW:
        assert {p.kind for p in library.get(number).paths} == {"pipe"}
