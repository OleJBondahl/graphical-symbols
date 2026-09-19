"""The linter: `lint(symbol)` runs every rule and applies the symbol's `lint_allow`."""

from collections.abc import Mapping
from dataclasses import replace

import deal

from graphical_symbols.geometry import Orientation
from graphical_symbols.lint.anchors import anchor_duplicate_id, anchor_off_geometry
from graphical_symbols.lint.connectivity import (
    node_invalid,
    path_invalid,
    port_isolated,
    through_axis,
    through_count,
    through_missing,
)
from graphical_symbols.lint.exemptions import allow_unknown, allow_unused, exempt
from graphical_symbols.lint.file import symbol_id_findings
from graphical_symbols.lint.geometry import degenerate, off_drawing_grid, text_too_large
from graphical_symbols.lint.ports import (
    port_duplicate_id,
    port_lane_clear,
    port_off_geometry,
    port_off_wiring_grid,
    port_on_body_edge,
    port_position_shared,
    port_spacing,
)
from graphical_symbols.lint.registry import (
    GUIDE_INDEX,
    RULE_IDS,
    RULES,
    Check,
    Rule,
    natural_key,
)
from graphical_symbols.lint.slots import (
    pitch_overflow,
    slot_missing,
    slot_overlap_body,
    slot_overlap_slot,
    slot_unknown_port,
)
from graphical_symbols.model import Finding, Symbol
from graphical_symbols.orient import orient

# One entry per rule that inspects a symbol; the rule's `Rule` row is in `registry.RULES`. The
# rest of `RULES` is computed elsewhere: the resolver's rules, and the two exemption rules below.
CHECKS: dict[str, Check] = {
    "id-format": symbol_id_findings,
    "off-drawing-grid": off_drawing_grid,
    "degenerate": degenerate,
    "text-too-large": text_too_large,
    "port-duplicate-id": port_duplicate_id,
    "port-off-wiring-grid": port_off_wiring_grid,
    "port-off-geometry": port_off_geometry,
    "port-on-body-edge": port_on_body_edge,
    "port-lane-clear": port_lane_clear,
    "port-spacing": port_spacing,
    "port-position-shared": port_position_shared,
    "node-invalid": node_invalid,
    "path-invalid": path_invalid,
    "through-count": through_count,
    "through-axis": through_axis,
    "through-missing": through_missing,
    "port-isolated": port_isolated,
    "slot-missing": slot_missing,
    "slot-unknown-port": slot_unknown_port,
    "slot-overlap-body": slot_overlap_body,
    "slot-overlap-slot": slot_overlap_slot,
    "pitch-overflow": pitch_overflow,
    "anchor-duplicate-id": anchor_duplicate_id,
    "anchor-off-geometry": anchor_off_geometry,
}

_ORIENTATION_INDEX: dict[Orientation | None, int] = {
    None: -1,
    **{orientation: index for index, orientation in enumerate(Orientation)},
}

__all__ = ["CHECKS", "RULES", "RULE_IDS", "Rule", "lint", "ordered", "run_checks"]


@deal.pure
def run_checks(
    symbol: Symbol, rules: Mapping[str, Rule], checks: Mapping[str, Check]
) -> tuple[Finding, ...]:
    """Run each check of a rule, before any exemption, and stamp the orientation.

    A rule that depends on the orientation is checked on `orient(symbol, o)` for each of the 8
    orientations, and its findings carry `o`. Any other rule is checked once on the symbol and
    its findings have no orientation. A rule without a check is skipped. The order is not final:
    see `ordered`.
    """
    found: list[Finding] = []
    for rule_id, rule in rules.items():
        if (check := checks.get(rule_id)) is None:
            continue
        if rule.orientation_dependent:
            found.extend(
                replace(f, orientation=o) for o in Orientation for f in check(orient(symbol, o))
            )
        else:
            found.extend(check(symbol))
    return tuple(found)


@deal.pure
def ordered(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    """Sort findings by the guide table's rule order, then orientation, then location.

    No orientation comes first, then R0 to MR270; locations sort with numbers as numbers. Findings
    that are equal on all three keep the order they came in.
    """
    return tuple(
        sorted(
            findings,
            key=lambda f: (
                GUIDE_INDEX[f.rule],
                _ORIENTATION_INDEX[f.orientation],
                natural_key(f.location or ""),
            ),
        )
    )


@deal.pure
def lint(symbol: Symbol) -> tuple[Finding, ...]:
    """Lint a flattened symbol in base orientation and return its findings.

    Every rule of `CHECKS` runs; the findings of each rule the symbol's `lint_allow` names are
    removed, whatever their severity or orientation; then `allow-unknown` and `allow-unused`
    report the exemptions themselves, and cannot be exempted. An exemption of a known rule is
    used when the rule fired in at least one orientation, judged before any exemption applies.

    Args:
        symbol: A resolved symbol in base orientation.

    Returns:
        The findings, ordered by the guide table's rule order, then orientation, then location.
    """
    raw = run_checks(symbol, RULES, CHECKS)
    return ordered(
        (
            *exempt(raw, symbol.lint_allow),
            *allow_unknown(symbol.lint_allow),
            *allow_unused(symbol.lint_allow, frozenset(f.rule for f in raw)),
        )
    )
