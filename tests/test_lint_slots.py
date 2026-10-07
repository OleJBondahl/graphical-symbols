"""Slots group: the five rules on text slots and the pole pitch."""

import math
from dataclasses import replace
from pathlib import Path

import pytest
from build_symbol import plain_symbol
from fixture_pipeline import run_fixture_by_file
from hypothesis import given, settings
from hypothesis import strategies as st

from symdef.files import load_library
from symdef.geometry import (
    Arc,
    Circle,
    Direction,
    Fill,
    Line,
    Orientation,
    Point,
    Polyline,
    Text,
)
from symdef.lint import CHECKS, RULES, lint
from symdef.lint.slots import (
    pitch_overflow,
    slot_missing,
    slot_overlap_body,
    slot_overlap_slot,
    slot_unknown_port,
)
from symdef.model import Allow, Port, Severity, Slot, SymbolKind
from symdef.model import Path as SymbolPath
from symdef.orient import orient

P = Point
N, E, S, W = Direction.N, Direction.E, Direction.S, Direction.W
GUIDE = Path(__file__).resolve().parent / "fixtures" / "guide"
SLOT_RULES = (
    "slot-missing",
    "slot-unknown-port",
    "slot-overlap-body",
    "slot-overlap-slot",
    "pitch-overflow",
)
ORIENTATION_DEPENDENT = {"slot-overlap-body", "slot-overlap-slot"}
SYMBOL = SymbolKind.SYMBOL


def where(findings):
    return [(f.rule, f.location) for f in findings]


def port(id_, x, y, direction):
    return Port(id_, P(x, y), direction)


def slot(id_, x, y, side, size):
    return Slot(id_, P(x, y), side, size)


IN_OUT = (port("in", 0, -2, N), port("out", 0, 2, S))
FULL_SLOTS = (
    slot("tag", -1.5, 0, W, (6, 1)),
    slot("marking.in", 0.25, -1.5, E, (1.5, 1)),
    slot("marking.out", 0.25, 1.5, E, (1.5, 1)),
)
THROUGH = (SymbolPath("in", "out", "switch_open", through=True),)


def a_symbol(**changes):
    """A kind = symbol file with both ports, a through path and every required slot."""
    fields = {"kind": SYMBOL, "ports": IN_OUT, "paths": THROUGH, "slots": FULL_SLOTS, **changes}
    return plain_symbol(**fields)


@pytest.fixture(scope="module")
def library():
    return load_library(GUIDE)


class TestRegistration:
    @pytest.mark.parametrize("rule_id", SLOT_RULES)
    def test_every_slots_rule_is_registered_with_a_check(self, rule_id):
        rule = RULES[rule_id]
        assert (rule.group, rule.severity) == ("Slots", Severity.ERROR)
        assert rule_id in CHECKS

    def test_only_the_two_overlap_rules_depend_on_the_orientation(self):
        dependent = {r for r in SLOT_RULES if RULES[r].orientation_dependent}
        assert dependent == ORIENTATION_DEPENDENT


DUTIES = ("tag", "marking.<port>")


def with_duties(symbol):
    """`slot_missing` with the duties the guide fixtures declare."""
    return slot_missing(symbol, DUTIES)


class TestSlotMissing:
    def test_a_symbol_with_a_tag_and_every_marking_is_clean(self):
        assert with_duties(a_symbol()) == ()

    def test_a_missing_tag_fires_at_the_tag_slot(self):
        symbol = a_symbol(slots=FULL_SLOTS[1:])
        (found,) = with_duties(symbol)
        assert (found.rule, found.severity, found.location) == (
            "slot-missing",
            Severity.ERROR,
            "slots.tag",
        )
        assert found.orientation is None
        assert "tag" in found.message

    def test_a_missing_marking_fires_at_the_missing_slot_and_names_the_port(self):
        symbol = a_symbol(slots=FULL_SLOTS[:2])
        (found,) = with_duties(symbol)
        assert found.location == "slots.marking.out"
        assert "'out'" in found.message

    def test_every_missing_slot_gets_its_own_finding(self):
        symbol = a_symbol(slots=())
        assert [f.location for f in with_duties(symbol)] == [
            "slots.tag",
            "slots.marking.in",
            "slots.marking.out",
        ]

    def test_a_symbol_without_ports_still_needs_a_tag(self):
        assert where(with_duties(plain_symbol(kind=SYMBOL))) == [("slot-missing", "slots.tag")]

    @pytest.mark.parametrize("kind", [SymbolKind.ELEMENT, SymbolKind.QUALIFIER])
    def test_other_kinds_are_exempt(self, kind):
        assert with_duties(a_symbol(kind=kind, slots=())) == ()

    def test_the_value_slot_is_optional_and_extra_slots_are_ignored(self):
        extra = (*FULL_SLOTS, slot("value", 0, 3, S, (1, 1)), slot("other", 0, 5, S, (1, 1)))
        assert with_duties(a_symbol(slots=extra)) == ()

    def test_a_marking_for_another_port_does_not_count(self):
        symbol = a_symbol(slots=(*FULL_SLOTS[:2], slot("marking.ghost", 0.25, 1.5, E, (1, 1))))
        assert where(with_duties(symbol)) == [("slot-missing", "slots.marking.out")]

    def test_slot_ids_are_compared_exactly(self):
        symbol = a_symbol(
            slots=(
                slot("Tag", 0, 0, W, (1, 1)),
                *FULL_SLOTS[1:2],
                slot("marking.OUT", 0, 0, E, (1, 1)),
            )
        )
        assert [f.location for f in with_duties(symbol)] == ["slots.tag", "slots.marking.out"]

    def test_a_port_id_with_dots_needs_the_dotted_marking_slot(self):
        symbol = plain_symbol(
            kind=SYMBOL,
            ports=(port("1.in", 0, -2, N),),
            slots=(slot("tag", 0, 0, W, (1, 1)), slot("marking.1.in", 0, 0, E, (1, 1))),
        )
        assert with_duties(symbol) == ()
        assert where(with_duties(replace(symbol, slots=symbol.slots[:1]))) == [
            ("slot-missing", "slots.marking.1.in")
        ]

    def test_ports_sharing_an_id_need_one_marking_slot_only(self):
        symbol = a_symbol(ports=(*IN_OUT, port("in", 3, -2, N)))
        assert with_duties(symbol) == ()
        assert len(with_duties(replace(symbol, slots=FULL_SLOTS[:1]))) == 2


class TestSlotUnknownPort:
    def test_markings_of_existing_ports_are_clean(self):
        assert slot_unknown_port(a_symbol()) == ()

    def test_a_marking_for_a_missing_port_fires_at_the_slot_and_names_it(self):
        symbol = a_symbol(slots=(*FULL_SLOTS, slot("marking.ghost", 0, 3, S, (1, 1))))
        (found,) = slot_unknown_port(symbol)
        assert (found.rule, found.severity, found.location) == (
            "slot-unknown-port",
            Severity.ERROR,
            "slots.marking.ghost",
        )
        assert found.orientation is None
        assert "'ghost'" in found.message

    @pytest.mark.parametrize("kind", list(SymbolKind))
    def test_every_kind_is_checked(self, kind):
        symbol = plain_symbol(kind=kind, slots=(slot("marking.x", 0, 0, E, (1, 1)),))
        assert where(slot_unknown_port(symbol)) == [("slot-unknown-port", "slots.marking.x")]

    @pytest.mark.parametrize(
        "slot_id", ["tag", "value", "marking", "markingx", "other", "Marking.x"]
    )
    def test_other_slot_ids_are_not_markings(self, slot_id):
        symbol = plain_symbol(slots=(slot(slot_id, 0, 0, E, (1, 1)),))
        assert slot_unknown_port(symbol) == ()

    def test_an_empty_port_name_is_unknown(self):
        symbol = plain_symbol(slots=(slot("marking.", 0, 0, E, (1, 1)),))
        assert where(slot_unknown_port(symbol)) == [("slot-unknown-port", "slots.marking.")]

    def test_ids_of_repeated_ports_match_on_everything_after_the_first_prefix(self):
        symbol = plain_symbol(
            ports=(port("1.in", 0, -2, N), port("2.in", 4, -2, N)),
            slots=(
                slot("marking.1.in", 0, 0, E, (1, 1)),
                slot("marking.2.in", 0, 0, E, (1, 1)),
                slot("marking.3.in", 0, 0, E, (1, 1)),
                slot("marking.in", 0, 0, E, (1, 1)),
            ),
        )
        assert [f.location for f in slot_unknown_port(symbol)] == [
            "slots.marking.3.in",
            "slots.marking.in",
        ]

    def test_only_the_first_marking_prefix_is_stripped(self):
        symbol = plain_symbol(
            ports=(port("marking.x", 0, 0, N),), slots=(slot("marking.marking.x", 0, 0, E, (1, 1)),)
        )
        assert slot_unknown_port(symbol) == ()


LEAD = (Line(P(0, -2), P(0, -1)),)


def with_slots(*slots, elements=LEAD, **changes):
    return plain_symbol(elements=elements, slots=slots, **changes)


class TestSlotOverlapBody:
    def test_no_slots_or_no_elements_are_clean(self):
        assert slot_overlap_body(plain_symbol()) == ()
        assert slot_overlap_body(with_slots(slot("a", 0, 0, E, (1, 1)), elements=())) == ()

    def test_a_slot_box_across_a_line_fires_at_the_slot_and_names_the_element(self):
        symbol = with_slots(slot("marking.in", -0.5, -1.5, E, (1.5, 1)))
        (found,) = slot_overlap_body(symbol)
        assert (found.rule, found.severity, found.location) == (
            "slot-overlap-body",
            Severity.ERROR,
            "slots.marking.in",
        )
        assert found.orientation is None
        assert "elements[0]" in found.message

    def test_a_box_beside_the_line_is_clean(self):
        assert slot_overlap_body(with_slots(slot("a", 0.25, -1.5, E, (1.5, 1)))) == ()

    def test_a_box_that_only_touches_along_an_edge_or_at_a_corner_is_clean(self):
        line = Line(P(0, -2), P(0, -1))
        assert slot_overlap_body(with_slots(slot("a", 0, -1, E, (1, 1)), elements=(line,))) == ()
        along = with_slots(slot("a", 0, -1.5, E, (1, 1)), elements=(line,))
        assert slot_overlap_body(along) == ()  # the line runs along the left edge
        corner = with_slots(slot("a", 0, -1, E, (1, 2)), elements=(Line(P(-1, 0), P(0, -1)),))
        assert slot_overlap_body(corner) == ()

    def test_one_grid_step_further_in_it_fires(self):
        line = Line(P(0, -2), P(0, -1))
        touching = with_slots(slot("a", 0, -1.5, E, (1, 1)), elements=(line,))
        moved = with_slots(slot("a", -0.125, -1.5, E, (1, 1)), elements=(line,))
        assert slot_overlap_body(touching) == ()
        assert where(slot_overlap_body(moved)) == [("slot-overlap-body", "slots.a")]

    def test_a_slot_inside_an_empty_closed_outline_is_clean(self):
        outline = Polyline((P(-3, -3), P(3, -3), P(3, 3), P(-3, 3)), closed=True)
        symbol = with_slots(slot("a", -1, 0, E, (2, 1)), elements=(outline,))
        assert slot_overlap_body(symbol) == ()

    def test_a_slot_inside_a_filled_outline_fires(self):
        filled = Polyline((P(-3, -3), P(3, -3), P(3, 3), P(-3, 3)), closed=True, fill=Fill.SOLID)
        symbol = with_slots(slot("a", -1, 0, E, (2, 1)), elements=(filled,))
        assert where(slot_overlap_body(symbol)) == [("slot-overlap-body", "slots.a")]

    def test_circles_arcs_and_text_are_overlapped_by_their_own_definitions(self):
        box = slot("a", 1, -0.5, E, (2, 1))
        for element in (
            Circle(P(2, 0), 0.5),
            Circle(P(2, 0), 0.5, Fill.SOLID),
            Arc(P(2, 0), 0.5, 0, 360 - 1),
            Text("M", P(2, 0), 1),
            Line(P(0, -0.5), P(4, -0.5)),
        ):
            assert slot_overlap_body(with_slots(box, elements=(element,))), element
        far = with_slots(box, elements=(Circle(P(6, 0), 0.5),))
        assert slot_overlap_body(far) == ()

    def test_a_circle_around_the_box_is_not_overlapped_unless_filled(self):
        box = slot("a", -0.5, -0.5, E, (1, 1))
        assert slot_overlap_body(with_slots(box, elements=(Circle(P(0, 0), 5),))) == ()
        assert slot_overlap_body(with_slots(box, elements=(Circle(P(0, 0), 5, Fill.SOLID),)))

    def test_one_finding_per_slot_naming_the_first_three_elements_and_counting_the_rest(self):
        lines = tuple(Line(P(0, -1.5 - i / 8), P(2, -1.5 - i / 8)) for i in range(5))
        symbol = with_slots(slot("a", 0, -1, N, (3, 3)), elements=lines)
        (found,) = slot_overlap_body(symbol)
        assert "elements[0], elements[1], elements[2] and 2 more" in found.message

    def test_each_slot_is_judged_on_its_own(self):
        symbol = with_slots(
            slot("a", -0.5, -1.5, E, (1, 1)),
            slot("b", 3, 3, E, (1, 1)),
            slot("c", -0.5, -1.25, E, (1, 1)),
        )
        assert [f.location for f in slot_overlap_body(symbol)] == ["slots.a", "slots.c"]

    def test_a_slot_box_without_area_overlaps_nothing(self):
        assert slot_overlap_body(with_slots(slot("a", 0, -1.5, E, (0, 1)))) == ()
        assert slot_overlap_body(with_slots(slot("a", 0, -1.5, E, (1, -1)))) == ()

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 1e300])
    def test_non_finite_and_huge_numbers_do_not_raise(self, bad):
        symbol = with_slots(slot("a", bad, 0, E, (1, bad)), slot("b", 0, bad, N, (bad, 1)))
        assert all(f.rule == "slot-overlap-body" for f in slot_overlap_body(symbol))


class TestSlotOverlapSlot:
    def test_disjoint_boxes_and_lone_slots_are_clean(self):
        assert slot_overlap_slot(plain_symbol()) == ()
        assert slot_overlap_slot(with_slots(slot("a", 0, 0, E, (1, 1)))) == ()
        assert (
            slot_overlap_slot(with_slots(slot("a", 0, 0, E, (1, 1)), slot("b", 5, 0, E, (1, 1))))
            == ()
        )

    def test_overlapping_boxes_fire_at_the_later_slot_and_name_both(self):
        symbol = with_slots(slot("a", 0, 0, E, (2, 1)), slot("b", 1, 0, E, (2, 1)))
        (found,) = slot_overlap_slot(symbol)
        assert (found.rule, found.severity, found.location) == (
            "slot-overlap-slot",
            Severity.ERROR,
            "slots.b",
        )
        assert found.orientation is None
        assert "'a'" in found.message
        assert "'b'" in found.message

    def test_boxes_that_touch_along_an_edge_or_at_a_corner_are_clean(self):
        assert (
            slot_overlap_slot(with_slots(slot("a", 0, 0, E, (1, 1)), slot("b", 1, 0, E, (1, 1))))
            == ()
        )
        assert (
            slot_overlap_slot(with_slots(slot("a", 0, 0, E, (1, 1)), slot("b", 0, 1, E, (1, 1))))
            == ()
        )
        assert (
            slot_overlap_slot(with_slots(slot("a", 0, 0, E, (1, 1)), slot("b", 1, 1, E, (1, 1))))
            == ()
        )

    def test_one_grid_step_of_overlap_fires(self):
        symbol = with_slots(slot("a", 0, 0, E, (1, 1)), slot("b", 0.875, 0, E, (1, 1)))
        assert where(slot_overlap_slot(symbol)) == [("slot-overlap-slot", "slots.b")]

    def test_a_box_inside_another_and_equal_boxes_overlap(self):
        inside = with_slots(slot("a", 0, 0, E, (4, 4)), slot("b", 1, 0, E, (1, 1)))
        equal = with_slots(slot("a", 0, 0, E, (1, 1)), slot("b", 0, 0, E, (1, 1)))
        assert slot_overlap_slot(inside)
        assert slot_overlap_slot(equal)

    def test_each_unordered_pair_is_reported_once(self):
        symbol = with_slots(
            slot("a", 0, 0, E, (2, 1)), slot("b", 0, 0, E, (2, 1)), slot("c", 0, 0, E, (2, 1))
        )
        assert [f.location for f in slot_overlap_slot(symbol)] == ["slots.b", "slots.c", "slots.c"]

    def test_the_sides_place_the_boxes(self):
        # a on the left of x = 0 and b on the right only touch; with N and S they do not
        assert (
            slot_overlap_slot(with_slots(slot("a", 0, 0, W, (1, 1)), slot("b", 0, 0, E, (1, 1))))
            == ()
        )
        assert (
            slot_overlap_slot(with_slots(slot("a", 0, 0, N, (1, 1)), slot("b", 0, 0, S, (1, 1))))
            == ()
        )
        assert slot_overlap_slot(with_slots(slot("a", 0, 0, N, (2, 2)), slot("b", 0, 0, E, (2, 2))))

    def test_a_slot_box_without_area_overlaps_nothing(self):
        assert (
            slot_overlap_slot(with_slots(slot("a", 0, 0, E, (0, 1)), slot("b", 0, 0, E, (2, 2))))
            == ()
        )

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 1e300])
    def test_non_finite_and_huge_numbers_do_not_raise(self, bad):
        symbol = with_slots(slot("a", bad, 0, E, (1, bad)), slot("b", 0, bad, N, (bad, 1)))
        assert all(f.rule == "slot-overlap-slot" for f in slot_overlap_slot(symbol))


def wide(marking_width, **changes):
    """A symbol with a through path whose `marking.in` slot is `marking_width` wide."""
    slots = (
        FULL_SLOTS[0],
        slot("marking.in", 0.25, -1.5, E, (marking_width, 1)),
        FULL_SLOTS[2],
    )
    body = (Line(P(0, -2), P(0, -1)), Line(P(0, 2), P(0, 1)), Line(P(0, 1), P(-1, -1)))
    return a_symbol(elements=body, slots=slots, **changes)


class TestPitchOverflow:
    def test_a_symbol_within_the_default_pitch_is_clean(self):
        assert pitch_overflow(wide(1.5)) == ()

    def test_an_extent_equal_to_the_pitch_is_clean_and_one_grid_step_more_fires(self):
        # the body reaches x = -1 and the marking slot x = 0.25 + width: 1 + 0.25 + 2.75 = 4
        assert pitch_overflow(wide(2.75)) == ()
        (found,) = pitch_overflow(wide(2.875))
        assert (found.rule, found.severity) == ("pitch-overflow", Severity.ERROR)
        assert found.orientation is None
        assert "4.125" in found.message

    def test_a_declared_pole_pitch_raises_the_limit(self):
        assert where(pitch_overflow(wide(5))) == [("pitch-overflow", None)]
        assert pitch_overflow(wide(5, pole_pitch=8)) == ()
        assert pitch_overflow(wide(6.75, pole_pitch=8)) == ()
        assert pitch_overflow(wide(6.875, pole_pitch=8))

    def test_the_tag_and_value_slots_are_left_out_of_the_extent(self):
        symbol = a_symbol(
            slots=(
                slot("tag", -20, 0, W, (6, 1)),
                *FULL_SLOTS[1:],
                slot("value", 20, 0, E, (6, 1)),
            )
        )
        assert pitch_overflow(symbol) == ()

    def test_any_other_slot_counts(self):
        symbol = a_symbol(slots=(*FULL_SLOTS, slot("other", 10, 3, E, (1, 1))))
        assert where(pitch_overflow(symbol)) == [("pitch-overflow", None)]

    def test_the_body_alone_can_be_too_wide(self):
        symbol = a_symbol(elements=(Line(P(-3, 0), P(3, 0)),), slots=())
        assert pitch_overflow(symbol)

    def test_only_the_x_extent_counts(self):
        symbol = a_symbol(elements=(Line(P(0, -50), P(0, 50)),), slots=())
        assert pitch_overflow(symbol) == ()

    def test_a_symbol_without_a_through_path_has_no_extent_to_check(self):
        assert pitch_overflow(replace(wide(5), paths=())) == ()
        assert pitch_overflow(replace(wide(5), paths=(replace(THROUGH[0], through=False),))) == ()

    def test_a_symbol_without_elements_and_slots_is_clean(self):
        assert pitch_overflow(a_symbol(elements=(), slots=())) == ()

    @pytest.mark.parametrize("kind", [SymbolKind.ELEMENT, SymbolKind.QUALIFIER])
    def test_other_kinds_are_exempt_even_with_a_bad_pole_pitch(self, kind):
        assert pitch_overflow(wide(9, kind=kind)) == ()
        assert pitch_overflow(wide(1.5, kind=kind, pole_pitch=6)) == ()

    @pytest.mark.parametrize("pitch", [4, 8, 12, 100])
    def test_a_positive_multiple_of_four_is_fine(self, pitch):
        assert pitch_overflow(wide(1.5, pole_pitch=pitch)) == ()

    @pytest.mark.parametrize("pitch", [3, 5, 6, 10, 0, -4, -8, 4.5, math.nan, math.inf, -math.inf])
    def test_any_other_pole_pitch_fires_at_pole_pitch(self, pitch):
        found = pitch_overflow(wide(1.5, pole_pitch=pitch))
        assert where(found) == [("pitch-overflow", "pole_pitch")]
        assert "multiple of 4" in found[0].message

    def test_a_bad_pole_pitch_needs_no_through_path(self):
        assert where(pitch_overflow(replace(wide(1.5, pole_pitch=6), paths=()))) == [
            ("pitch-overflow", "pole_pitch")
        ]

    def test_a_bad_but_positive_pole_pitch_is_still_the_limit_of_the_extent(self):
        assert where(pitch_overflow(wide(3.5, pole_pitch=6))) == [("pitch-overflow", "pole_pitch")]
        assert len(pitch_overflow(wide(5.5, pole_pitch=6))) == 2  # extent 6.75 > 6

    def test_a_pole_pitch_that_is_not_positive_leaves_the_default_of_four(self):
        assert len(pitch_overflow(wide(5, pole_pitch=0))) == 2
        assert len(pitch_overflow(wide(5, pole_pitch=-4))) == 2
        assert len(pitch_overflow(wide(1.5, pole_pitch=math.nan))) == 1

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 1e300])
    def test_non_finite_and_huge_numbers_do_not_raise(self, bad):
        symbol = a_symbol(
            elements=(Line(P(bad, 0), P(0, bad)),),
            slots=(slot("a", bad, 0, E, (1, bad)), slot("b", 0, bad, N, (bad, 1))),
            pole_pitch=bad,
        )
        assert all(f.rule == "pitch-overflow" for f in pitch_overflow(symbol))

    def test_lint_runs_it_once_in_the_base_orientation(self):
        found = [f for f in lint(wide(2.875)) if f.rule == "pitch-overflow"]
        assert [f.orientation for f in found] == [None]


def orientations_of(findings):
    return {f.orientation for f in findings}


class TestOrientationOnlyFixtures:
    @pytest.mark.parametrize("rule_id", sorted(ORIENTATION_DEPENDENT))
    def test_the_orientation_only_case_fires_only_outside_the_base_orientation(self, rule_id):
        findings = run_fixture_by_file(rule_id)["S00002"]
        assert {f.rule for f in findings} == {rule_id}
        orientations = orientations_of(findings)
        assert orientations
        assert Orientation.R0 not in orientations
        assert None not in orientations

    @pytest.mark.parametrize("rule_id", sorted(ORIENTATION_DEPENDENT))
    def test_the_ordinary_case_fires_in_the_base_orientation(self, rule_id):
        findings = run_fixture_by_file(rule_id)["S00001"]
        assert Orientation.R0 in orientations_of(findings)

    def test_the_slot_fixtures_boxes_overlap_after_a_quarter_turn(self):
        symbol = orient(
            plain_symbol(
                slots=(slot("a", 2, 2, E, (3, 1)), slot("b", 2, 4, E, (3, 1))),
            ),
            Orientation.R90,
        )
        assert where(slot_overlap_slot(symbol)) == [("slot-overlap-slot", "slots.b")]


class TestOverlapRulesInEveryOrientation:
    def test_lint_stamps_each_orientation_the_rule_fires_in(self):
        symbol = plain_symbol(
            slots=(slot("a", 2, 2, E, (3, 1)), slot("b", 2, 4, E, (3, 1))),
        )
        found = [f for f in lint(symbol) if f.rule == "slot-overlap-slot"]
        assert {f.orientation for f in found} == {
            Orientation.R90,
            Orientation.R270,
            Orientation.MR90,
            Orientation.MR270,
        }

    def test_an_exemption_covers_the_orientations_the_rule_fires_in_and_is_used(self):
        symbol = plain_symbol(
            slots=(slot("a", 2, 2, E, (3, 1)), slot("b", 2, 4, E, (3, 1))),
            lint_allow=(Allow("slot-overlap-slot", "a test"),),
        )
        assert lint(symbol) == ()

    def test_an_exemption_of_a_rule_that_fires_in_no_orientation_is_unused(self):
        symbol = plain_symbol(lint_allow=(Allow("slot-overlap-body", "a test"),))
        assert where(lint(symbol)) == [("allow-unused", "lint_allow[0]")]


class TestFixtures:
    @pytest.mark.parametrize("rule_id", SLOT_RULES)
    def test_the_fixture_findings_of_the_rule_have_the_registrys_severity(self, rule_id):
        found = [f for fs in run_fixture_by_file(rule_id).values() for f in fs if f.rule == rule_id]
        assert found
        assert {f.severity for f in found} == {Severity.ERROR}

    def test_the_slot_missing_fixture_has_a_case_without_a_tag_and_one_without_a_marking(self):
        found = run_fixture_by_file("slot-missing")
        assert [f.location for f in found["S00001"] if f.rule == "slot-missing"] == ["slots.tag"]
        assert [f.location for f in found["S00002"] if f.rule == "slot-missing"] == [
            "slots.marking.out"
        ]

    def test_the_pitch_overflow_fixture_has_a_case_for_each_way_to_fire(self):
        found = run_fixture_by_file("pitch-overflow")
        assert [f.location for f in found["S00001"]] == [None]
        assert [f.location for f in found["S00002"]] == ["pole_pitch"]
        assert [f.location for f in found["S00003"]] == ["pole_pitch"]


class TestGuideExamples:
    @pytest.mark.parametrize("number", ["S00227", "S00230", "S00305", "S00171", "S00016"])
    def test_the_guide_examples_trip_no_slots_rule(self, library, number):
        assert [
            f for f in lint(library.get(number), library.required_slots) if f.rule in SLOT_RULES
        ] == []

    def test_the_connection_points_missing_slots_are_the_ones_it_exempts(self, library):
        found = slot_missing(library.get("S00016"), library.required_slots)
        assert [f.location for f in found] == [
            "slots.tag",
            "slots.marking.n",
            "slots.marking.e",
            "slots.marking.s",
            "slots.marking.w",
        ]


class TestInvariantRulesInEveryOrientation:
    @given(
        st.sampled_from(list(Orientation)),
        st.sampled_from(
            [FULL_SLOTS, FULL_SLOTS[1:], (*FULL_SLOTS, slot("marking.g", 0, 3, S, (1, 1)))]
        ),
    )
    @settings(max_examples=40, deadline=None)
    def test_the_slot_id_rules_do_not_change_when_the_symbol_is_oriented(self, orientation, slots):
        symbol = a_symbol(slots=slots)
        turned = orient(symbol, orientation)
        for check in (with_duties, slot_unknown_port):
            assert where(check(turned)) == where(check(symbol))

    def test_a_slot_box_keeps_its_size_when_the_symbol_turns(self):
        symbol = orient(a_symbol(), Orientation.R90)
        assert {s.box for s in symbol.slots} == {(6, 1), (1.5, 1)}
