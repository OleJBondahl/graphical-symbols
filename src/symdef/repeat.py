"""Repeat a symbol along +x: the only multi-pole mechanism."""

from dataclasses import replace

import deal

from symdef.geometry import Element, Line, Point, Style, Weight
from symdef.model import Node, Path, Port, Slot, Symbol, nodes_of
from symdef.orient import translate

_DEFAULT_PITCH = 4
_LINK = "link"
_MARKING = "marking."


@deal.pure
def _pole_elements(elements: tuple[Element, ...], k: int) -> tuple[Element, ...]:
    """Return pole `k`'s elements, a bound lead's `port` prefixed `<k>.` to match its port."""
    return tuple(
        replace(e, port=f"{k}.{e.port}") if isinstance(e, Line) and e.port is not None else e
        for e in elements
    )


@deal.pure
def _pole_slots(slots: tuple[Slot, ...], k: int) -> tuple[Slot, ...]:
    """Return the slots pole `k` contributes: its marking slots renamed, the rest from pole 1."""
    return tuple(
        replace(s, id=f"{_MARKING}{k}.{s.id.removeprefix(_MARKING)}")
        if s.id.startswith(_MARKING)
        else s
        for s in slots
        if k == 1 or s.id.startswith(_MARKING)
    )


@deal.pure
def _pole_parts(
    pole: Symbol, k: int
) -> tuple[tuple[Port, ...], tuple[Node, ...], tuple[Path, ...]]:
    """Return the ports, nodes and paths of pole `k` with every port id prefixed by `<k>.`."""
    return (
        tuple(replace(p, id=f"{k}.{p.id}") for p in pole.ports),
        tuple(replace(n, ports=tuple(f"{k}.{p}" for p in n.ports)) for n in nodes_of(pole)),
        tuple(
            replace(
                p,
                from_port=f"{k}.{p.from_port}",
                to_port=f"{k}.{p.to_port}",
                through=p.through and k == 1,
            )
            for p in pole.paths
        ),
    )


@deal.pure
@deal.pre(lambda symbol, n: n >= 1)  # noqa: ARG005
@deal.pre(lambda symbol, n: any(p.through for p in symbol.paths))  # noqa: ARG005
def repeat(symbol: Symbol, n: int) -> Symbol:
    """Return `n` copies of a symbol placed along +x, as an ordinary symbol.

    Pole k (from 1) is the symbol translated by `((k - 1) * pitch, 0)`, where the pitch is the
    symbol's `pole_pitch`, default 4. Ports, and the paths, nodes and bound leads that name them,
    are prefixed `<k>.`; every node is listed explicitly, `potential` kept. Marking slots
    (`marking.in` becomes
    `marking.<k>.in`) repeat per pole; `tag`, `value` and any other slot come from pole 1 only.
    Only pole 1's path keeps `through`. Pole 1's anchors become the result's anchors, and if one
    is `link` and `n > 1` a dashed line joins pole 1's `link` to pole n's. `pole_pitch` becomes
    `n * pitch`; everything else is carried over.

    Args:
        symbol: A symbol in base orientation with a through path.
        n: The pole count, at least 1.

    Returns:
        The repeated symbol; with `n = 1` it is the symbol with renamed ports and slots.
    """
    pitch = symbol.pole_pitch or _DEFAULT_PITCH
    poles = tuple(translate(symbol, (k - 1) * pitch, 0) for k in range(1, n + 1))
    parts = tuple(_pole_parts(pole, k) for k, pole in enumerate(poles, start=1))
    link = next((a for a in symbol.anchors if a.id == _LINK), None)
    dashes = ()
    if link is not None and n > 1:
        end = Point(link.position.x + (n - 1) * pitch, link.position.y)
        dashes = (Line(link.position, end, Weight.NORMAL, Style.DASHED),)
    return replace(
        symbol,
        elements=tuple(
            e for k, pole in enumerate(poles, start=1) for e in _pole_elements(pole.elements, k)
        )
        + dashes,
        ports=tuple(p for ports, _, _ in parts for p in ports),
        nodes=tuple(node for _, nodes, _ in parts for node in nodes),
        paths=tuple(path for _, _, paths in parts for path in paths),
        anchors=poles[0].anchors,
        slots=tuple(s for k, pole in enumerate(poles, start=1) for s in _pole_slots(pole.slots, k)),
        pole_pitch=n * pitch,
    )
