"""The symbol data model: frozen values, deliberately without validation."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import Enum

import deal

from symdef.errors import UnknownSymbolError
from symdef.geometry import Direction, Element, Orientation, Point


class Status(Enum):
    """Whether a symbol's geometry was checked against the standard's own drawing."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class SymbolKind(Enum):
    """Whether a symbol is placeable on its own or exists to be used as a part."""

    SYMBOL = "symbol"
    ELEMENT = "element"
    QUALIFIER = "qualifier"


class PathKind(Enum):
    """The electrical meaning of a path between two nodes."""

    CONDUCTOR = "conductor"
    SWITCH_OPEN = "switch_open"
    SWITCH_CLOSED = "switch_closed"
    IMPEDANCE = "impedance"
    SOURCE = "source"
    DIODE = "diode"


class Potential(Enum):
    """The fixed potential a node stands for."""

    EARTH = "earth"
    PROTECTIVE_EARTH = "protective_earth"
    FUNCTIONAL_EARTH = "functional_earth"
    FRAME = "frame"


class Severity(Enum):
    """How serious a finding is; a data repo gate rejects both."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Port:
    """A connection point on a symbol; the id is the only pin identity.

    Attributes:
        position: Where a wire meets the symbol, in module units.
        direction: The outward normal: the side of the body box the port sits on.
        description: Free text, empty if none.
    """

    id: str
    position: Point
    direction: Direction
    description: str = ""


@dataclass(frozen=True, slots=True)
class Node:
    """Ports that are the same electrical point inside the symbol.

    Attributes:
        ports: Port ids.
        potential: The fixed potential the node stands for, or None for an ordinary node.
    """

    ports: tuple[str, ...]
    potential: Potential | None = None


@dataclass(frozen=True, slots=True)
class Path:
    """A two-terminal relation between the ports of two different nodes.

    Attributes:
        from_port: Id of the port at one end.
        to_port: Id of the port at the other end.
        kind: The electrical meaning of the relation.
        through: Whether this is the symbol's through path, the one `repeat` requires and
            keeps on pole 1 only.
    """

    from_port: str
    to_port: str
    kind: PathKind
    through: bool = False


@dataclass(frozen=True, slots=True)
class Anchor:
    """An attachment point for composition.

    Attributes:
        position: In module units.
        direction: The way the anchor faces; two anchors join when they face each other.
    """

    id: str
    position: Point
    direction: Direction


@dataclass(frozen=True, slots=True)
class Slot:
    """Room reserved for text the consumer draws; `box` is (width, height).

    Attributes:
        position: The point the box grows from, in module units.
        side: The direction the box grows towards from `position`; see `slot_box`.
        box: Width and height in module units, never rotated.
    """

    id: str
    position: Point
    side: Direction
    box: tuple[float, float]


@dataclass(frozen=True, slots=True)
class Reference:
    """Where a symbol is defined in its standard."""

    standard: str
    number: str
    edition: str | None = None
    form: str | None = None


@dataclass(frozen=True, slots=True)
class Allow:
    """A lint exemption with its reason."""

    rule: str
    reason: str


@dataclass(frozen=True, slots=True)
class Symbol:
    """A symbol definition, not a placement: it has no label, tag or position.

    Attributes:
        name: The symbol's name.
        reference: Where the standard defines it.
        elements: The drawing, in module units.
        pole_pitch: Spacing between poles for `repeat`, in module units; None means 4.
        lint_allow: Lint exemptions the symbol claims.
    """

    name: str
    kind: SymbolKind
    status: Status
    reference: Reference
    elements: tuple[Element, ...]
    ports: tuple[Port, ...] = ()
    nodes: tuple[Node, ...] = ()
    paths: tuple[Path, ...] = ()
    anchors: tuple[Anchor, ...] = ()
    slots: tuple[Slot, ...] = ()
    pole_pitch: int | None = None
    lint_allow: tuple[Allow, ...] = ()


@dataclass(frozen=True, slots=True)
class Finding:
    """One lint or load problem.

    Attributes:
        rule: The id of the rule that reported it.
        message: Human-readable text.
        location: Where it is, such as `elements[2]` or `slots.tag`, or None if it is about the
            whole symbol.
        orientation: The orientation it was found in, or None if the rule does not depend on
            orientation.
    """

    rule: str
    severity: Severity
    message: str
    location: str | None = None
    orientation: Orientation | None = None


@dataclass(frozen=True, slots=True)
class LibraryConfig:
    """The standard-specific settings from `library.toml`."""

    standard: str
    title: str
    number_pattern: str
    package: str = ""


@dataclass(frozen=True, slots=True)
class Library:
    """The symbols of one standard, keyed by reference number.

    Iterating yields the symbols sorted by reference number; `len` is their count.
    """

    standard: str
    title: str
    number_pattern: str
    symbols: Mapping[str, Symbol]

    def get(self, number: str) -> Symbol:
        """Return the symbol with this reference number.

        Raises:
            UnknownSymbolError: If the library has no such symbol.
        """
        try:
            return self.symbols[number]
        except KeyError:
            msg = f"no symbol {number!r} in {self.standard}"
            raise UnknownSymbolError(msg) from None

    def __iter__(self) -> Iterator[Symbol]:
        """Yield the symbols sorted by reference number."""
        return (self.symbols[number] for number in sorted(self.symbols))

    def __len__(self) -> int:
        """Return the number of symbols."""
        return len(self.symbols)


@deal.pure
def nodes_of(symbol: Symbol) -> tuple[Node, ...]:
    """Return every node of a symbol: the declared ones, then one per port in no declared node.

    Ports named twice, or named by a node but absent from `ports`, are kept as declared; the
    linter reports them.
    """
    listed = {port_id for node in symbol.nodes for port_id in node.ports}
    alone = tuple(Node((port.id,)) for port in symbol.ports if port.id not in listed)
    return (*symbol.nodes, *alone)
