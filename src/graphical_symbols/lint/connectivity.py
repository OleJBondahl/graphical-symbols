"""Connectivity-group rules: nodes, paths and the through path (guide sections 3, 5 and 8)."""

import deal

from graphical_symbols.geometry import Direction
from graphical_symbols.lint.registry import quote, rule_finding
from graphical_symbols.model import Finding, Port, Symbol, SymbolKind, nodes_of

_PAIR = 2


@deal.pure
def _first_node_of(symbol: Symbol) -> dict[str, int]:
    """Map each port id to the index in `nodes_of` of the first node that lists it."""
    first: dict[str, int] = {}
    for index, node in enumerate(nodes_of(symbol)):
        for port_id in node.ports:
            first.setdefault(port_id, index)
    return first


@deal.pure
def _first_port_of(symbol: Symbol) -> dict[str, Port]:
    """Map each port id to the first port that has it."""
    first: dict[str, Port] = {}
    for port in symbol.ports:
        first.setdefault(port.id, port)
    return first


@deal.pure
def node_invalid(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every place a declared node names an unknown port or lists a port a second time.

    A port named again by the same node counts as listed twice. One finding per offending name, at
    the node that names it (`nodes[i]`), so a port listed by three nodes gives two findings.
    """
    known = {port.id for port in symbol.ports}
    listed_at: dict[str, int] = {}
    found: list[Finding] = []
    for index, node in enumerate(symbol.nodes):
        for port_id in node.ports:
            if port_id not in known:
                message = f"the node names the unknown port {quote(port_id)}"
            elif port_id in listed_at:
                message = (
                    f"the port {quote(port_id)} is already listed by nodes[{listed_at[port_id]}]"
                )
            else:
                listed_at[port_id] = index
                continue
            found.append(rule_finding("node-invalid", message, f"nodes[{index}]"))
    return tuple(found)


@deal.pure
def path_invalid(symbol: Symbol) -> tuple[Finding, ...]:
    """Report paths that name an unknown port, join one node to itself or repeat a path.

    Nodes come from `nodes_of`, so a port in no declared node is a node of its own, and a port
    listed by two nodes belongs to the first. One finding per path, at `paths[i]`: an unknown port
    first, then two ports of one node; a repeat of an earlier path between the same two nodes
    (in either direction) is reported at the later path and names the earlier one. A path that
    joins one node to itself does not count as an earlier path.
    """
    known = {port.id for port in symbol.ports}
    node_of = _first_node_of(symbol)
    seen: dict[frozenset[int], int] = {}
    found: list[Finding] = []
    for index, path in enumerate(symbol.paths):
        unknown = [
            quote(p) for p in dict.fromkeys((path.from_port, path.to_port)) if p not in known
        ]
        message = None
        if unknown:
            message = f"the path names the unknown port {' and '.join(unknown)}"
        else:
            pair = frozenset((node_of[path.from_port], node_of[path.to_port]))
            if len(pair) == 1:
                message = (
                    f"the path joins {quote(path.from_port)} and {quote(path.to_port)}, "
                    "two ports of one node"
                )
            elif pair in seen:
                message = f"the path repeats paths[{seen[pair]}], between the same two nodes"
            else:
                seen[pair] = index
        if message is not None:
            found.append(rule_finding("path-invalid", message, f"paths[{index}]"))
    return tuple(found)


@deal.pure
def through_count(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every through path after the first, at the later path, naming the first."""
    through = [index for index, path in enumerate(symbol.paths) if path.through]
    return tuple(
        rule_finding(
            "through-count",
            f"paths[{through[0]}] is already the through path; a symbol has at most one",
            f"paths[{index}]",
        )
        for index in through[1:]
    )


@deal.pure
def _axis_problem(from_port: Port, to_port: Port) -> str | None:
    """Return why two ports are not `(0, -a)` N and `(0, a)` S, `a` a positive whole number."""
    a = to_port.position.y
    if not (a > 0 and a % 1 == 0):
        return f"the distance {a!r} is not a positive whole number of modules"
    if from_port.position.x != 0 or to_port.position.x != 0 or from_port.position.y != -a:
        return "the ports are not at (0, -a) and (0, a)"
    if from_port.direction is not Direction.N or to_port.direction is not Direction.S:
        return "the ports do not face N and S"
    return None


@deal.pure
def through_axis(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every through path whose ports are not `(0, -a)` N (from) and `(0, a)` S (to).

    `a` is a positive whole number of modules, the same for both ports. Exact comparisons, base
    orientation only. Every through path is checked, whatever `through-count` says; a path that
    names an unknown port is left to `path-invalid`. At `paths[i]`.
    """
    ports = _first_port_of(symbol)
    found: list[Finding] = []
    for index, path in enumerate(symbol.paths):
        from_port, to_port = ports.get(path.from_port), ports.get(path.to_port)
        if not path.through or from_port is None or to_port is None:
            continue
        if (problem := _axis_problem(from_port, to_port)) is not None:
            message = (
                f"the through path from {quote(path.from_port)} to {quote(path.to_port)} "
                f"is off the axis: {problem}"
            )
            found.append(rule_finding("through-axis", message, f"paths[{index}]"))
    return tuple(found)


@deal.pure
def through_missing(symbol: Symbol) -> tuple[Finding, ...]:
    """Warn for a kind-symbol file with two or more nodes, no potential and no through path."""
    nodes = nodes_of(symbol)
    if (
        symbol.kind is SymbolKind.SYMBOL
        and len(nodes) >= _PAIR
        and not any(node.potential is not None for node in nodes)
        and not any(path.through for path in symbol.paths)
    ):
        message = f"{len(nodes)} nodes, no potential and no through path"
        return (rule_finding("through-missing", message),)
    return ()


@deal.pure
def port_isolated(symbol: Symbol) -> tuple[Finding, ...]:
    """Warn for every port in no path, in no multi-port node, whose node has no potential.

    A multi-port node is a declared node that lists two or more different existing ports. A port
    listed by two nodes takes the first. One finding per port, at `ports[i]`.
    """
    known = {port.id for port in symbol.ports}
    in_path = {port_id for path in symbol.paths for port_id in (path.from_port, path.to_port)}
    joined = {
        port_id
        for node in symbol.nodes
        if len(set(node.ports) & known) >= _PAIR
        for port_id in node.ports
    }
    nodes = nodes_of(symbol)
    first_node = _first_node_of(symbol)
    return tuple(
        rule_finding(
            "port-isolated",
            f"the port {quote(port.id)} is in no path, in no multi-port node and its node has "
            "no potential",
            f"ports[{index}]",
        )
        for index, port in enumerate(symbol.ports)
        if port.id not in in_path
        and port.id not in joined
        and nodes[first_node[port.id]].potential is None
    )
