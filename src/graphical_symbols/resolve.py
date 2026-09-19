"""Resolve symbol files into flattened symbols: parts, placement and inheritance (guide section 7).

Problems are returned as findings per file stem, never raised. A file whose parts cannot be used
(a part file that is unknown, in a cycle, or itself broken) gets no symbol, and only the file that
is at fault reports; the files that use it say nothing.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

import deal

from graphical_symbols.geometry import Element, Line, Orientation, Point, Style, Weight
from graphical_symbols.lint.file import metadata_findings, part_id_findings
from graphical_symbols.lint.registry import quote, rule_finding
from graphical_symbols.load import symbol_from_data, validate
from graphical_symbols.model import (
    Anchor,
    Finding,
    LibraryConfig,
    Node,
    Path,
    Port,
    Slot,
    Symbol,
    nodes_of,
)
from graphical_symbols.orient import orient, translate
from graphical_symbols.repeat import repeat

_PLACEMENT_KEYS = ("to", "length", "via")

# One file's parts being resolved: the file stem and the index of the part in progress.
_Stack = tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class Resolution:
    """The flattened symbols and the findings of a library, both keyed by file stem."""

    symbols: Mapping[str, Symbol]
    findings: Mapping[str, tuple[Finding, ...]]


@dataclass(frozen=True, slots=True)
class _Walk:
    """The state of one `resolve_library` call; the two dicts are filled as the walk goes."""

    sources: Mapping[str, Mapping[str, Any]]
    valid: frozenset[str]
    resolved: dict[str, Symbol | None]
    problems: dict[str, list[Finding]]


@deal.pure
def _at(*keys: str | int) -> str:
    """Make a JSON Pointer, escaping `~` and `/` in the keys."""
    return "".join("/" + str(key).replace("~", "~0").replace("/", "~1") for key in keys)


@deal.pure
def _order(finding: Finding) -> tuple[str, str]:
    """Sort by rule, then by location with numbers in natural order (`/parts/2` before `/10`)."""
    location = re.sub(r"\d+", lambda m: f"{len(m.group()):04d}{m.group()}", finding.location or "")
    return finding.rule, location


@deal.pure
def _form_findings(data: Mapping[str, Any]) -> tuple[Finding, ...]:
    """Report the forms `validate` accepts but only one kind of file may use.

    `ports` is an array of tables in an atomic file and a rename table in a composite; a slot is
    a string reference only in a composite.
    """
    ports = data.get("ports")
    if "parts" in data:
        if isinstance(ports, list):
            return (
                rule_finding(
                    "schema", "a file with parts exports its ports through a rename table", "/ports"
                ),
            )
        return ()
    found = []
    if isinstance(ports, dict):
        found.append(
            rule_finding(
                "schema", "a file without parts lists its ports as an array of tables", "/ports"
            )
        )
    found += [
        rule_finding("schema", "a slot reference needs parts to refer to", _at("slots", key))
        for key, slot in data.get("slots", {}).items()
        if isinstance(slot, str)
    ]
    return tuple(found)


@deal.pure
def _prepare(
    index: int, part: Mapping[str, Any], base: Symbol
) -> tuple[Symbol | None, tuple[Finding, ...]]:
    """Apply the part's `repeat` first and its `orient` second.

    `repeat` states its preconditions as contracts, so they are checked here and reported as
    `schema` findings at the `repeat` key.
    """
    symbol = base
    if "repeat" in part:
        where = _at("parts", index, "repeat")
        count = int(part["repeat"])
        if count < 1:
            return None, (rule_finding("schema", "repeat must be at least 1", where),)
        if not any(path.through for path in base.paths):
            return None, (rule_finding("schema", "repeat needs a part with a through path", where),)
        symbol = repeat(base, count)
    return orient(symbol, Orientation(part.get("orient", "R0"))), ()


@deal.pure
def _anchor(symbol: Symbol, anchor_id: str) -> Anchor | None:
    """Return the symbol's anchor with this id, if it has one."""
    return next((a for a in symbol.anchors if a.id == anchor_id), None)


@deal.pure
def _target(
    index: int, to: str, placed: Mapping[str, Symbol], failed: frozenset[str]
) -> tuple[Anchor | None, tuple[Finding, ...]]:
    """Find the target anchor `part.anchor`, which must be an anchor of an earlier part.

    A target on a part that itself failed to place is not reported again.
    """
    where = _at("parts", index, "to")
    part_id, _, anchor_id = to.partition(".")
    if part_id in failed:
        return None, ()
    if part_id not in placed:
        return None, (
            rule_finding(
                "part-anchor",
                f"to {quote(to)} must be 'part.anchor' naming an earlier part",
                where,
            ),
        )
    anchor = _anchor(placed[part_id], anchor_id)
    if anchor is None:
        return None, (
            rule_finding(
                "part-anchor", f"part {quote(part_id)} has no anchor {quote(anchor_id)}", where
            ),
        )
    return anchor, ()


@deal.pure
def _attach(
    index: int,
    part: Mapping[str, Any],
    oriented: Symbol,
    placed: Mapping[str, Symbol],
    failed: frozenset[str],
) -> tuple[Symbol | None, tuple[Element, ...], tuple[Finding, ...]]:
    """Place a part by anchor: translate it by `T + length * dT - A`; `via` adds the link line."""
    where = _at("parts", index)
    if "to" not in part:
        return None, (), (rule_finding("part-anchor", "attach needs to", f"{where}/attach"),)
    target, found = _target(index, part["to"], placed, failed)
    own = _anchor(oriented, part["attach"])
    length = part.get("length", 0)
    problems = list(found)
    if own is None:
        problems.append(
            rule_finding(
                "part-anchor",
                f"the part has no anchor {quote(part['attach'])}",
                f"{where}/attach",
            )
        )
    if "via" in part and not length > 0:
        problems.append(
            rule_finding("part-anchor", "via needs a length greater than 0", f"{where}/via")
        )
    if target is not None and own is not None and own.direction != target.direction.opposite:
        problems.append(
            rule_finding("part-anchor", "the anchors do not face each other after orient", where)
        )
    if problems or target is None or own is None:
        return None, (), tuple(problems)
    tip = Point(
        target.position.x + length * target.direction.dx + 0.0,
        target.position.y + length * target.direction.dy + 0.0,
    )
    moved = translate(oriented, tip.x - own.position.x, tip.y - own.position.y)
    link = (Line(target.position, tip, Weight.NORMAL, Style.DASHED),) if "via" in part else ()
    return moved, link, ()


@deal.pure
def _place(
    index: int,
    part: Mapping[str, Any],
    oriented: Symbol,
    placed: Mapping[str, Symbol],
    failed: frozenset[str],
) -> tuple[Symbol | None, tuple[Element, ...], tuple[Finding, ...]]:
    """Place an oriented part: by `at`, by `attach`, or (first part only) at the origin.

    Returns the moved part, the link line `via` adds, and the findings; no part with findings.
    """
    where = _at("parts", index)
    if "at" in part:
        if "attach" in part or any(key in part for key in _PLACEMENT_KEYS):
            message = "at cannot be combined with attach, to, length or via"
            return None, (), (rule_finding("part-anchor", message, where),)
        x, y = part["at"]
        return translate(oriented, x, y), (), ()
    if "attach" in part:
        return _attach(index, part, oriented, placed, failed)
    if any(key in part for key in _PLACEMENT_KEYS):
        message = "to, length and via need attach"
        return None, (), (rule_finding("part-anchor", message, where),)
    if index > 0:
        message = "a part after the first needs exactly one of attach or at"
        return None, (), (rule_finding("part-anchor", message, where),)
    return oriented, (), ()


@deal.pure
def _place_parts(
    parts: list[Mapping[str, Any]], bases: Mapping[str, Symbol]
) -> tuple[dict[str, Symbol], tuple[Element, ...], tuple[Finding, ...]]:
    """Place every part in file order.

    Returns the placed parts by local id, the elements of all parts (a part's link line before
    the part's own elements), and the findings. A part that fails to place is left out and its
    id is remembered, so a later part that targets it adds no finding of its own.
    """
    placed: dict[str, Symbol] = {}
    failed: set[str] = set()
    elements: list[Element] = []
    found: list[Finding] = []
    for index, part in enumerate(parts):
        name = part["as"]
        if name in placed or name in failed:
            found.append(
                rule_finding(
                    "schema", f"duplicate part id {quote(name)}", _at("parts", index, "as")
                )
            )
            continue
        oriented, problems = _prepare(index, part, bases[part["use"]])
        moved, link = None, ()
        if oriented is not None:
            moved, link, problems = _place(index, part, oriented, placed, frozenset(failed))
        if moved is None:
            failed.add(name)
            found += problems
        else:
            placed[name] = moved
            elements += (*link, *moved.elements)
    return placed, tuple(elements), tuple(found)


@deal.pure
def _export_ports(
    exports: Mapping[str, str], placed: Mapping[str, Symbol]
) -> tuple[tuple[Port, ...], dict[str, list[str]], tuple[Finding, ...]]:
    """Build the composite's ports from its rename map.

    Returns the ports, the new ids each `part.port` is exported as, and the findings: an
    `export-unknown` for a target that is no part port and a `part-port-unexported` for a part
    port the map leaves out.
    """
    available = {f"{name}.{p.id}": p for name, part in placed.items() for p in part.ports}
    ports: list[Port] = []
    exported: dict[str, list[str]] = {}
    found: list[Finding] = []
    for new_id, ref in exports.items():
        port = available.get(ref)
        if port is None:
            message = f"the port {quote(new_id)} names {quote(ref)}, which is no port of a part"
            found.append(rule_finding("export-unknown", message, _at("ports", new_id)))
        else:
            ports.append(replace(port, id=new_id))
            exported.setdefault(ref, []).append(new_id)
    found += [
        rule_finding(
            "part-port-unexported", f"the port {quote(ref)} of a part is not exported", "/ports"
        )
        for ref in available
        if ref not in exported
    ]
    return tuple(ports), exported, tuple(found)


@deal.pure
def _export_slots(
    slots: Mapping[str, Any], placed: Mapping[str, Symbol], own: Symbol
) -> tuple[tuple[Slot, ...], tuple[Finding, ...]]:
    """Build the composite's slots in declaration order.

    A string is a reference `part.slot` to a slot of a placed part (the slot id itself may
    contain dots, so it splits at the first one); a table is a new slot, already read into `own`.
    """
    declared = {s.id: s for s in own.slots}
    result: list[Slot] = []
    found: list[Finding] = []
    for key, value in slots.items():
        if not isinstance(value, str):
            result.append(declared[key])
            continue
        part_id, _, slot_id = value.partition(".")
        source = (
            next((s for s in placed[part_id].slots if s.id == slot_id), None)
            if part_id in placed
            else None
        )
        if source is None:
            message = f"the slot {quote(key)} names {quote(value)}, which is no slot of a part"
            found.append(rule_finding("export-unknown", message, _at("slots", key)))
        else:
            result.append(replace(source, id=key))
    return tuple(result), tuple(found)


@deal.pure
def _inherit_nodes(
    placed: Mapping[str, Symbol], exported: Mapping[str, list[str]], own: tuple[Node, ...]
) -> tuple[Node, ...]:
    """Inherit every part node through the renames; an own node restating one adds its potential."""
    nodes = [
        Node(ports, node.potential)
        for name, part in placed.items()
        for node in nodes_of(part)
        if (ports := tuple(new for p in node.ports for new in exported.get(f"{name}.{p}", ())))
    ]
    for declared in own:
        same = next((i for i, n in enumerate(nodes) if set(n.ports) == set(declared.ports)), None)
        if same is None:
            nodes.append(declared)
        else:
            nodes[same] = Node(nodes[same].ports, declared.potential or nodes[same].potential)
    return tuple(nodes)


@deal.pure
def _inherit_paths(
    placed: Mapping[str, Symbol],
    exported: Mapping[str, list[str]],
    nodes: tuple[Node, ...],
    own: tuple[Path, ...],
) -> tuple[Path, ...]:
    """Inherit every part path through the renames, then apply the composite's own paths.

    An own path replaces the inherited path between the same nodes. When more than one path is
    inherited as `through`, the flag is cleared on all of them; the composite's own paths keep
    theirs, which is how it redeclares the one that stays.
    """
    inherited = [
        replace(path, from_port=start[0], to_port=end[0])
        for name, part in placed.items()
        for path in part.paths
        if (start := exported.get(f"{name}.{path.from_port}"))
        and (end := exported.get(f"{name}.{path.to_port}"))
    ]
    if sum(path.through for path in inherited) > 1:
        inherited = [replace(path, through=False) for path in inherited]
    node_of = {port: i for i, node in enumerate(nodes) for port in node.ports}

    def between(path: Path) -> frozenset[int | None]:
        return frozenset((node_of.get(path.from_port), node_of.get(path.to_port)))

    replaced = {between(path) for path in own}
    return (*(path for path in inherited if between(path) not in replaced), *own)


@deal.pure
def _compose(
    data: Mapping[str, Any], bases: Mapping[str, Symbol]
) -> tuple[Symbol | None, tuple[Finding, ...]]:
    """Flatten a composite whose part files are all resolved (`bases`, by file stem).

    Kind, status, reference, name, anchors, `pole_pitch` and `lint_allow` are the composite's
    own, read by `symbol_from_data`, which skips the rename map and slot references read here.
    """
    placed, elements, found = _place_parts(data["parts"], bases)
    if found:
        return None, found
    own = symbol_from_data(data)
    ports, exported, port_findings = _export_ports(data.get("ports", {}), placed)
    slots, slot_findings = _export_slots(data.get("slots", {}), placed, own)
    found = (*port_findings, *slot_findings)
    if found:
        return None, found
    nodes = _inherit_nodes(placed, exported, own.nodes)
    return (
        replace(
            own,
            elements=(*elements, *own.elements),
            ports=ports,
            nodes=nodes,
            paths=_inherit_paths(placed, exported, nodes, own.paths),
            slots=slots,
        ),
        (),
    )


@deal.pure
def _report_cycle(walk: _Walk, here: _Stack, use: str) -> None:
    """Report `part-cycle` on every file of the cycle `use` closes, at the part that leads on."""
    members = here[[stem for stem, _ in here].index(use) :]
    chain = " -> ".join((*(stem for stem, _ in members), use))
    for stem, index in members:
        walk.problems[stem].append(
            rule_finding("part-cycle", f"parts form a cycle: {chain}", _at("parts", index, "use"))
        )


@deal.pure
def _visit_composite(
    walk: _Walk, stem: str, data: Mapping[str, Any], stack: _Stack
) -> Symbol | None:
    """Resolve the parts of a composite, reporting the unknown and the cyclic, then compose it."""
    bases: dict[str, Symbol] = {}
    usable = True
    for index, part in enumerate(data["parts"]):
        use = part["use"]
        here = (*stack, (stem, index))
        if use not in walk.sources:
            message = f"the part file {quote(use)} does not exist"
            walk.problems[stem].append(
                rule_finding("part-unknown", message, _at("parts", index, "use"))
            )
            usable = False
        elif any(name == use for name, _ in here):
            _report_cycle(walk, here, use)
            usable = False
        elif use in walk.valid and (base := _visit(walk, use, here)) is not None:
            bases[use] = base
        else:
            usable = False
    if not usable:
        return None
    symbol, found = _compose(data, bases)
    walk.problems[stem].extend(found)
    return symbol


@deal.pure
def _visit(walk: _Walk, stem: str, stack: _Stack) -> Symbol | None:
    """Resolve one schema-valid file once: atomic files as read, composites flattened."""
    if stem not in walk.resolved:
        data = walk.sources[stem]
        walk.resolved[stem] = (
            _visit_composite(walk, stem, data, stack) if "parts" in data else symbol_from_data(data)
        )
    return walk.resolved[stem]


@deal.pure
def resolve_library(config: LibraryConfig, sources: Mapping[str, Mapping[str, Any]]) -> Resolution:
    """Validate, check and flatten every file of a library.

    A file that fails validation has `schema` findings and no symbol. Otherwise it is checked for
    `metadata` and `id-format`, and resolved: atomic files as read, composites flattened with
    their parts placed and their ports, nodes, paths and slots inherited as section 7 says. A
    symbol with only `metadata` or `id-format` findings still resolves.

    Args:
        config: The library's `library.toml`.
        sources: Decoded TOML or JSON data, keyed by file stem.

    Returns:
        The symbols by file stem, sorted, and the findings of the stems that have any, sorted by
        stem and within a stem by rule and location.
    """
    stems = sorted(sources)
    problems: dict[str, list[Finding]] = {}
    valid: set[str] = set()
    for stem in stems:
        data = sources[stem]
        broken = validate(data) or _form_findings(data)
        if broken:
            problems[stem] = list(broken)
        else:
            valid.add(stem)
            problems[stem] = [*metadata_findings(stem, data, config), *part_id_findings(data)]
    walk = _Walk(sources, frozenset(valid), {}, problems)
    for stem in stems:
        if stem in valid:
            _visit(walk, stem, ())
    return Resolution(
        {stem: symbol for stem in stems if (symbol := walk.resolved.get(stem)) is not None},
        {stem: tuple(sorted(found, key=_order)) for stem, found in problems.items() if found},
    )
