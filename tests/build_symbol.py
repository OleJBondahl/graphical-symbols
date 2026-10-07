"""A minimal `Symbol` for the rule tests: one line, no ports, and whatever the test changes."""

from dataclasses import replace

from symdef.geometry import Line, Point
from symdef.model import Reference, Status, Symbol, SymbolKind

PLAIN = Symbol(
    name="Plain",
    kind=SymbolKind.ELEMENT,
    status=Status.UNVERIFIED,
    reference=Reference("IEC 60617", "S00001"),
    elements=(Line(Point(0, 0), Point(0, 1)),),
)


def plain_symbol(**changes) -> Symbol:
    """Return `PLAIN` with the given fields replaced."""
    return replace(PLAIN, **changes)
