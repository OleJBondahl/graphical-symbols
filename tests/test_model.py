import dataclasses

import pytest

from symdef.errors import GraphicalSymbolsError, LibraryError, UnknownSymbolError
from symdef.geometry import Direction, Line, Orientation, Point
from symdef.model import (
    Anchor,
    Finding,
    Library,
    Node,
    Path,
    PathKind,
    Port,
    Potential,
    Reference,
    Severity,
    Slot,
    Status,
    Symbol,
    SymbolKind,
    nodes_of,
)


def sym(number="1", **fields):
    return Symbol(
        name="t",
        kind=SymbolKind.SYMBOL,
        status=Status.UNVERIFIED,
        reference=Reference("X", number),
        elements=(Line(Point(0, 0), Point(1, 0)),),
        **fields,
    )


def port(port_id, direction=Direction.N):
    return Port(port_id, Point(0, 0), direction)


def test_enum_values_are_the_file_spellings():
    assert [s.value for s in Status] == ["unverified", "verified"]
    assert [k.value for k in SymbolKind] == ["symbol", "element", "qualifier"]
    assert [k.value for k in PathKind] == [
        "conductor",
        "switch_open",
        "switch_closed",
        "impedance",
        "source",
        "diode",
    ]
    assert [p.value for p in Potential] == [
        "earth",
        "protective_earth",
        "functional_earth",
        "frame",
    ]
    assert [s.value for s in Severity] == ["error", "warning"]


def test_symbol_defaults():
    s = sym()
    assert s.ports == ()
    assert s.nodes == ()
    assert s.paths == ()
    assert s.anchors == ()
    assert s.slots == ()
    assert s.pole_pitch is None
    assert s.lint_allow == ()


def test_small_type_defaults():
    assert Port("in", Point(0, 0), Direction.N).description == ""
    assert Node(("in",)).potential is None
    assert Path("in", "out", PathKind.CONDUCTOR).through is False
    assert Reference("X", "1").edition is None
    assert Reference("X", "1").form is None
    assert Finding("r", Severity.ERROR, "m").location is None
    assert Finding("r", Severity.ERROR, "m").orientation is None


def test_finding_carries_orientation():
    assert Finding("r", Severity.WARNING, "m", "a", Orientation.MR90).orientation is (
        Orientation.MR90
    )


def test_model_types_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        sym().name = "x"


def test_malformed_symbols_are_constructible():
    empty = Symbol("", SymbolKind.ELEMENT, Status.VERIFIED, Reference("", ""), ())
    assert empty.elements == ()
    odd = sym(
        ports=(port("a"), port("a")),
        nodes=(Node(("ghost",)),),
        paths=(Path("a", "a", PathKind.SOURCE, through=True),),
        anchors=(Anchor("k", Point(0.3, 0), Direction.W),),
        slots=(Slot("tag", Point(0, 0), Direction.E, (-1.0, 0.0)),),
    )
    assert len(odd.ports) == 2


def test_nodes_of_without_ports_or_nodes_is_empty():
    assert nodes_of(sym()) == ()


def test_nodes_of_gives_each_unlisted_port_its_own_node_in_port_order():
    s = sym(ports=(port("b"), port("a"), port("c")))
    assert nodes_of(s) == (Node(("b",)), Node(("a",)), Node(("c",)))


def test_nodes_of_keeps_declared_nodes_first_then_the_rest():
    declared = Node(("c", "a"), Potential.FRAME)
    s = sym(ports=(port("a"), port("b"), port("c"), port("d")), nodes=(declared,))
    assert nodes_of(s) == (declared, Node(("b",)), Node(("d",)))


def test_nodes_of_synthetic_nodes_have_no_potential():
    assert all(n.potential is None for n in nodes_of(sym(ports=(port("a"),))))


def test_nodes_of_keeps_malformed_declarations_as_declared():
    twice = (Node(("a", "b")), Node(("b", "ghost")))
    s = sym(ports=(port("a"), port("b")), nodes=twice)
    assert nodes_of(s) == twice
    dup = sym(ports=(port("x"), port("x")))
    assert nodes_of(dup) == (Node(("x",)), Node(("x",)))
    assert nodes_of(sym(ports=(port("x"), port("x")), nodes=(Node(("x",)),))) == (Node(("x",)),)


def test_library_get_returns_the_symbol_and_raises_when_unknown():
    a = sym("S00001")
    lib = Library("X", "t", r"^S\d{5}$", {"S00001": a})
    assert lib.get("S00001") is a
    with pytest.raises(UnknownSymbolError):
        lib.get("S99999")


def test_library_iterates_sorted_by_number_and_has_a_length():
    symbols = {n: sym(n) for n in ("S00030", "S00002", "S00100")}
    lib = Library("X", "t", "", symbols)
    assert [s.reference.number for s in lib] == ["S00002", "S00030", "S00100"]
    assert len(lib) == 3
    assert len(Library("X", "t", "", {})) == 0


def test_error_hierarchy():
    assert issubclass(UnknownSymbolError, GraphicalSymbolsError)
    assert issubclass(LibraryError, GraphicalSymbolsError)


def test_library_error_carries_its_findings():
    findings = (
        Finding("schema", Severity.ERROR, "bad key"),
        Finding("metadata", Severity.ERROR, "x"),
    )
    error = LibraryError(findings)
    assert error.findings == findings
    assert "schema" in str(error)
    assert "bad key" in str(error)
