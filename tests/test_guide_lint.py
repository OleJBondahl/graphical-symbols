"""The guide's examples lint clean with all 34 rules, alone and repeated (sections 4 and 12)."""

import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from graphical_symbols.boxes import body_box, slot_box
from graphical_symbols.build import load_library
from graphical_symbols.lint import lint
from graphical_symbols.load import parse_config
from graphical_symbols.model import Severity, Slot
from graphical_symbols.repeat import repeat
from graphical_symbols.resolve import resolve_library

GUIDE = Path(__file__).resolve().parent / "fixtures" / "guide"
CLEAN = ["S00227", "S00230", "S00305", "S00016", "S00171"]
WITH_A_THROUGH_PATH = ["S00227", "S00230", "S00305"]


@pytest.fixture(scope="module")
def library():
    return load_library(GUIDE)


def pole_extent(symbol):
    """The x extent of section 8 point 6, worked out here from the boxes, not by the rule."""
    boxes = [body_box(symbol), *(slot_box(s) for s in symbol.slots if s.id not in ("tag", "value"))]
    return max(b.max.x for b in boxes) - min(b.min.x for b in boxes)


@pytest.mark.parametrize("number", CLEAN)
def test_the_atomic_examples_and_the_qualifier_lint_to_nothing(library, number):
    assert lint(library.get(number)) == ()


def test_the_connection_point_uses_every_exemption_it_declares(library):
    symbol = library.get("S00016")
    assert {a.rule for a in symbol.lint_allow} == {
        "port-on-body-edge",
        "port-lane-clear",
        "slot-missing",
    }
    without = lint(replace(symbol, lint_allow=()))
    assert {f.rule for f in without} == {"port-on-body-edge", "port-lane-clear", "slot-missing"}


class TestPushButton:
    """S00254 fails `pitch-overflow` as written: concern C1."""

    def test_it_produces_exactly_one_finding_pitch_overflow(self, library):
        (found,) = lint(library.get("S00254"))
        assert (found.rule, found.severity) == ("pitch-overflow", Severity.ERROR)
        assert found.orientation is None
        assert "5.0 M" in found.message
        assert "pole pitch of 4 M" in found.message

    def test_its_extent_is_the_number_concern_c1_records(self, library):
        symbol = library.get("S00254")
        assert symbol.pole_pitch is None
        assert body_box(symbol).min.x == -3.25
        assert pole_extent(symbol) == 5.0
        assert pole_extent(symbol) >= 4.25

    def test_with_a_pole_pitch_of_eight_added_to_the_source_it_lints_clean(self):
        config, _ = parse_config((GUIDE / "library.toml").read_text(encoding="utf-8"))
        assert config is not None
        sources = {
            path.stem: tomllib.loads(path.read_text(encoding="utf-8"))
            for path in sorted((GUIDE / "symbols").glob("*.toml"))
        }
        sources["S00254"]["pole_pitch"] = 8
        resolution = resolve_library(config, sources)
        assert resolution.findings == {}
        assert resolution.symbols["S00254"].pole_pitch == 8
        assert lint(resolution.symbols["S00254"]) == ()

    def test_the_variant_is_the_only_change_needed(self, library):
        symbol = replace(library.get("S00254"), pole_pitch=8)
        assert lint(symbol) == ()

    def test_the_check_can_fail_at_the_boundary(self, library):
        symbol = replace(library.get("S00254"), pole_pitch=4)
        assert [f.rule for f in lint(symbol)] == ["pitch-overflow"]
        assert lint(replace(symbol, pole_pitch=8)) == ()


class TestRepeatedExamples:
    @pytest.mark.parametrize("poles", [1, 2, 3])
    @pytest.mark.parametrize("number", WITH_A_THROUGH_PATH)
    def test_a_repeated_example_lints_clean(self, library, number, poles):
        assert lint(repeat(library.get(number), poles)) == ()

    def test_the_relay_coil_is_exactly_as_wide_as_its_pitch(self, library):
        symbol = library.get("S00305")
        assert pole_extent(symbol) == 4
        assert symbol.pole_pitch is None

    def test_a_coil_whose_marking_reaches_a_grid_step_past_its_body_would_not_repeat(self, library):
        symbol = library.get("S00305")
        wider = replace(
            symbol,
            slots=tuple(
                Slot(s.id, s.position, s.side, (1.875, s.box[1])) if s.id == "marking.in" else s
                for s in symbol.slots
            ),
        )
        assert pole_extent(wider) == 4.125
        assert [f.rule for f in lint(repeat(wider, 3))] == ["pitch-overflow"]

    def test_the_change_over_contact_repeats_at_its_own_pitch(self, library):
        repeated = repeat(library.get("S00230"), 3)
        assert repeated.pole_pitch == 24
        assert lint(repeated) == ()
