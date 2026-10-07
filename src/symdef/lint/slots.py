"""Slots-group rules: text slots, their boxes and the pole pitch (guide sections 6 and 8)."""

import deal

from symdef.boxes import body_box, slot_box
from symdef.lint.overlap import boxes_overlap, overlaps_rect
from symdef.lint.registry import quote, rule_finding
from symdef.model import Finding, Symbol, SymbolKind

_MARKING = "marking."
_PORT = "<port>"
_NAMED_OFFENDERS = 3
_DEFAULT_PITCH = 4
_LEFT_OUT_OF_THE_EXTENT = ("tag", "value")


@deal.pure
def _missing(entry: str, port_id: str) -> str:
    """Return the message for a required slot that is missing; `port_id` is for `<port>` entries."""
    if _PORT not in entry:
        return f"the file has no {entry} slot"
    return f"the file has no {entry.split(_PORT)[0].rstrip('.')} slot for the port {quote(port_id)}"


@deal.pure
def slot_missing(symbol: Symbol, required_slots: tuple[str, ...] = ()) -> tuple[Finding, ...]:
    """Report each declared slot a `kind = "symbol"` file lacks; with none declared, no duty.

    `required_slots` is the set's `[rules] required_slots`: a slot id, or one with `<port>` in it
    (`marking.<port>`), which asks for one slot per port id. One finding per missing slot, at that
    slot (`slots.tag`, `slots.marking.<port id>`); ports that share an id need one slot.
    """
    if symbol.kind is not SymbolKind.SYMBOL:
        return ()
    have = {slot.id for slot in symbol.slots}
    port_ids = dict.fromkeys(port.id for port in symbol.ports)
    wanted = [
        (entry.replace(_PORT, port_id), _missing(entry, port_id))
        for entry in required_slots
        for port_id in (port_ids if _PORT in entry else ("",))
    ]
    return tuple(
        rule_finding("slot-missing", message, f"slots.{slot_id}")
        for slot_id, message in wanted
        if slot_id not in have
    )


@deal.pure
def slot_unknown_port(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every marking slot whose port id is not a port of the symbol.

    A marking slot is one whose id starts `marking.`; the rest of the id is the port id, so the
    ports `1.in` and `2.in` of a repeated symbol have the slots `marking.1.in` and `marking.2.in`.
    """
    known = {port.id for port in symbol.ports}
    return tuple(
        rule_finding(
            "slot-unknown-port",
            f"the marking slot names the port {quote(slot.id.removeprefix(_MARKING))}, "
            "which the symbol does not have",
            f"slots.{slot.id}",
        )
        for slot in symbol.slots
        if slot.id.startswith(_MARKING) and slot.id.removeprefix(_MARKING) not in known
    )


@deal.pure
def slot_overlap_body(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every slot box that overlaps an element, by the guide's definition of overlap.

    Touching along an edge or at a corner is not overlap, and an unfilled closed outline is only
    its outline, so a slot may sit inside an empty body rectangle. One finding per slot, at
    `slots.<id>`, naming the first few elements. Slot boxes do not rotate with the symbol, so the
    driver runs this rule in each of the 8 orientations.
    """
    found: list[Finding] = []
    for slot in symbol.slots:
        box = slot_box(slot)
        offenders = [
            f"elements[{i}]" for i, e in enumerate(symbol.elements) if overlaps_rect(e, box)
        ]
        if offenders:
            named = ", ".join(offenders[:_NAMED_OFFENDERS])
            more = len(offenders) - _NAMED_OFFENDERS
            message = f"the slot box of {quote(slot.id)} overlaps {named}" + (
                f" and {more} more" if more > 0 else ""
            )
            found.append(rule_finding("slot-overlap-body", message, f"slots.{slot.id}"))
    return tuple(found)


@deal.pure
def slot_overlap_slot(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every pair of slot boxes that overlap, once, at the later slot of the pair.

    Open interiors: boxes that only touch do not overlap, and a box without area overlaps
    nothing. The driver runs this rule in each of the 8 orientations.
    """
    boxes = [slot_box(slot) for slot in symbol.slots]
    return tuple(
        rule_finding(
            "slot-overlap-slot",
            f"the slot boxes of {quote(symbol.slots[earlier].id)} and {quote(slot.id)} overlap",
            f"slots.{slot.id}",
        )
        for later, slot in enumerate(symbol.slots)
        for earlier in range(later)
        if boxes_overlap(boxes[earlier], boxes[later])
    )


@deal.pure
def pitch_overflow(symbol: Symbol) -> tuple[Finding, ...]:
    """Report a bad `pole_pitch` and a symbol that is too wide for its pole pitch.

    Only for `kind = "symbol"`, in base orientation. A `pole_pitch` that is not a positive
    multiple of 4 is a finding at `pole_pitch`. For a symbol with a through path the x extent of
    the body box united with every slot box except `tag` and `value` must be at most the pole
    pitch (4 if there is none); a `pole_pitch` that is positive but not a multiple of 4 is still
    the limit, and one that is not positive leaves the default of 4.
    """
    if symbol.kind is not SymbolKind.SYMBOL:
        return ()
    pitch = symbol.pole_pitch
    found: list[Finding] = []
    if pitch is not None and not (pitch > 0 and pitch % _DEFAULT_PITCH == 0):
        message = f"the pole pitch {pitch!r} is not a positive multiple of {_DEFAULT_PITCH}"
        found.append(rule_finding("pitch-overflow", message, "pole_pitch"))
    if any(path.through for path in symbol.paths):
        limit = pitch if pitch is not None and pitch > 0 else _DEFAULT_PITCH
        boxes = (
            body_box(symbol),
            *(slot_box(s) for s in symbol.slots if s.id not in _LEFT_OUT_OF_THE_EXTENT),
        )
        extent = max(b.max.x for b in boxes) - min(b.min.x for b in boxes)
        if extent > limit:
            message = (
                f"the x extent of the body box and the slot boxes other than tag and value is "
                f"{extent!r} M, more than the pole pitch of {limit!r} M"
            )
            found.append(rule_finding("pitch-overflow", message))
    return tuple(found)
