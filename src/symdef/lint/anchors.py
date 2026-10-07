"""Anchors-group rules: `anchor-duplicate-id` and `anchor-off-geometry`."""

from symdef.lint.geometry import point_on_geometry
from symdef.lint.registry import quote, rule_finding
from symdef.model import Finding, Symbol


def anchor_duplicate_id(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every anchor whose id an earlier anchor already has, at the later anchor."""
    first_seen: dict[str, int] = {}
    found: list[Finding] = []
    for index, anchor in enumerate(symbol.anchors):
        if anchor.id in first_seen:
            first = first_seen[anchor.id]
            message = f"the anchor id {quote(anchor.id)} is already used by anchors[{first}]"
            found.append(rule_finding("anchor-duplicate-id", message, f"anchors[{index}]"))
        else:
            first_seen[anchor.id] = index
    return tuple(found)


def anchor_off_geometry(symbol: Symbol) -> tuple[Finding, ...]:
    """Warn about every anchor that lies on no element.

    An anchor is on an element when it is on a line or polyline segment, on a circle or arc, on a
    closed outline, or inside a filled shape; a text element does not count.
    """
    return tuple(
        rule_finding(
            "anchor-off-geometry",
            f"the anchor {quote(anchor.id)} lies on no element",
            f"anchors[{index}]",
        )
        for index, anchor in enumerate(symbol.anchors)
        if not point_on_geometry(anchor.position, symbol.elements)
    )
