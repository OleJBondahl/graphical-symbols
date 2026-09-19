"""Ports-group rules: the wiring contract at each port (guide section 8, points 1 to 3 and 5)."""

import deal

from graphical_symbols.boxes import body_box, keepout_box, slot_box
from graphical_symbols.geometry import Box, Direction, Point
from graphical_symbols.lint.geometry import point_on_geometry
from graphical_symbols.lint.overlap import boxes_overlap, overlaps_rect, wire_lane
from graphical_symbols.lint.registry import quote, rule_finding
from graphical_symbols.model import Finding, Port, Symbol, nodes_of

# How far past the symbol's own extent the finite frame of a wire lane reaches, in module units.
_LANE_MARGIN = 1.0
_NAMED_OFFENDERS = 3
_WIRING_GRID = 1
_SPACING = 2


@deal.pure
def _lane_frame(symbol: Symbol) -> Box:
    """Return a box that holds every element, slot box and port, grown by the lane margin.

    A wire lane is unbounded; clipped to this box it still reaches past all of the symbol's
    geometry, so it meets exactly what the unbounded lane would.
    """
    keepout = keepout_box(symbol)
    xs = (keepout.min.x, keepout.max.x, *(p.position.x for p in symbol.ports))
    ys = (keepout.min.y, keepout.max.y, *(p.position.y for p in symbol.ports))
    return Box(
        Point(min(xs) - _LANE_MARGIN, min(ys) - _LANE_MARGIN),
        Point(max(xs) + _LANE_MARGIN, max(ys) + _LANE_MARGIN),
    )


@deal.pure
def port_lane_clear(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every port whose wire lane an element or a slot box overlaps.

    The lane is the open region `P + t * d + u * n`, `t > 0`, `|u| < 0.25`. A lead that ends at the
    port (`t = 0`) or a box 0.25 M beside the wire only touches it. One finding per port, at
    `ports[i]`, naming the first few offenders. Slot boxes do not rotate with the symbol, so the
    driver runs this rule in each of the 8 orientations.
    """
    frame = _lane_frame(symbol)
    found: list[Finding] = []
    for index, port in enumerate(symbol.ports):
        lane = wire_lane(port.position, port.direction, frame)
        offenders = [
            *(f"elements[{i}]" for i, e in enumerate(symbol.elements) if overlaps_rect(e, lane)),
            *(f"slots.{s.id}" for s in symbol.slots if boxes_overlap(slot_box(s), lane)),
        ]
        if offenders:
            named = ", ".join(offenders[:_NAMED_OFFENDERS])
            more = len(offenders) - _NAMED_OFFENDERS
            message = f"the wire lane of the port {quote(port.id)} is overlapped by {named}" + (
                f" and {more} more" if more > 0 else ""
            )
            found.append(rule_finding("port-lane-clear", message, f"ports[{index}]"))
    return tuple(found)


@deal.pure
def port_duplicate_id(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every port whose id an earlier port already has, at the later port."""
    first_seen: dict[str, int] = {}
    found: list[Finding] = []
    for index, port in enumerate(symbol.ports):
        if port.id in first_seen:
            message = (
                f"the port id {quote(port.id)} is already used by ports[{first_seen[port.id]}]"
            )
            found.append(rule_finding("port-duplicate-id", message, f"ports[{index}]"))
        else:
            first_seen[port.id] = index
    return tuple(found)


@deal.pure
def port_off_wiring_grid(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every port whose position is not a whole number of modules, exactly.

    NaN and infinity are not whole numbers. One finding per port, naming each coordinate that is
    off.
    """
    found: list[Finding] = []
    for index, port in enumerate(symbol.ports):
        off = [
            f"{axis} {value!r}"
            for axis, value in (("x", port.position.x), ("y", port.position.y))
            if value % _WIRING_GRID != 0
        ]
        if off:
            message = f"the port {quote(port.id)} is not on the 1 M wiring grid: {', '.join(off)}"
            found.append(rule_finding("port-off-wiring-grid", message, f"ports[{index}]"))
    return tuple(found)


@deal.pure
def port_off_geometry(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every port that is not the free end of a lead or on an outline.

    A port is on geometry at either end of a line or of an open polyline, anywhere on a circle, an
    arc or a closed polyline's outline, and (decision D5) inside a filled circle or a filled
    closed polyline; a text element is not geometry. This is `point_on_geometry` with
    `endpoints_only`, so a bend in an open polyline does not count.
    """
    return tuple(
        rule_finding(
            "port-off-geometry",
            f"the port {quote(port.id)} is not at the end of a line or open polyline, and not on "
            "a circle, an arc or a closed outline",
            f"ports[{index}]",
        )
        for index, port in enumerate(symbol.ports)
        if not point_on_geometry(port.position, symbol.elements, endpoints_only=True)
    )


@deal.pure
def _on_matching_side(port: Port, body: Box) -> bool:
    """Return whether a port lies, exactly, on the side of the box its direction points out of."""
    x, y = port.position.x, port.position.y
    across_x = body.min.x <= x <= body.max.x
    across_y = body.min.y <= y <= body.max.y
    match port.direction:
        case Direction.N:
            return y == body.min.y and across_x
        case Direction.S:
            return y == body.max.y and across_x
        case Direction.E:
            return x == body.max.x and across_y
        case Direction.W:
            return x == body.min.x and across_y


@deal.pure
def port_on_body_edge(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every port that is not on the body-box side its direction is the outward normal of.

    North is `y == min.y`, south `y == max.y`, east `x == max.x` and west `x == min.x`, with the
    other coordinate inside the side. The comparison is exact. Text boxes do not turn with the
    symbol, so the driver runs this rule in each of the 8 orientations.
    """
    body = body_box(symbol)
    return tuple(
        rule_finding(
            "port-on-body-edge",
            f"the port {quote(port.id)} faces {port.direction.name} but is not on that side of "
            "the body box",
            f"ports[{index}]",
        )
        for index, port in enumerate(symbol.ports)
        if not _on_matching_side(port, body)
    )


@deal.pure
def _along_side(port: Port) -> float:
    """Return the coordinate that is measured along the side a port faces: x for N and S."""
    return port.position.x if port.direction in (Direction.N, Direction.S) else port.position.y


@deal.pure
def port_spacing(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every port that is not a multiple of 2 M from an earlier port with the same `dir`.

    The distance is measured along the side: x for N and S ports, y for E and W ports. Exact; ports
    at one coordinate are 0 apart and fine. One finding per later port, naming the first earlier
    port it is out of step with.
    """
    found: list[Finding] = []
    for later, port in enumerate(symbol.ports):
        for earlier in symbol.ports[:later]:
            gap = _along_side(port) - _along_side(earlier)
            if earlier.direction is port.direction and gap % _SPACING != 0:
                message = (
                    f"the ports {quote(earlier.id)} and {quote(port.id)} both face "
                    f"{port.direction.name} and are {abs(gap)!r} M apart along the side, "
                    f"which is not a multiple of {_SPACING} M"
                )
                found.append(rule_finding("port-spacing", message, f"ports[{later}]"))
                break
    return tuple(found)


@deal.pure
def port_position_shared(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every port that shares a position with an earlier port of another node.

    Ports of one node may share a position. A port in no declared node is a node of its own, and
    a port id listed twice belongs to the first node that lists it; two ports with one id are one
    node. One finding per later port, naming the first earlier port of another node at its position.
    """
    node_of: dict[str, int] = {}
    for index, node in enumerate(nodes_of(symbol)):
        for port_id in node.ports:
            node_of.setdefault(port_id, index)
    found: list[Finding] = []
    for later, port in enumerate(symbol.ports):
        for earlier in symbol.ports[:later]:
            if earlier.position == port.position and node_of[earlier.id] != node_of[port.id]:
                message = (
                    f"the port {quote(port.id)} is at the same position as the port "
                    f"{quote(earlier.id)} of another node"
                )
                found.append(rule_finding("port-position-shared", message, f"ports[{later}]"))
                break
    return tuple(found)
