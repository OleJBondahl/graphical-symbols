"""The round-trip check: a resolved dict must read back as the symbol it came from."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from graphical_symbols.load import symbol_from_data
from graphical_symbols.model import Slot, Symbol, nodes_of
from graphical_symbols.serialize import symbol_to_data


def _slot_id(slot: Slot) -> str:
    return slot.id


def normalised(symbol: Symbol) -> Symbol:
    """Make the two things resolved JSON changes explicit: every node listed, slots sorted by id."""
    return replace(symbol, nodes=nodes_of(symbol), slots=tuple(sorted(symbol.slots, key=_slot_id)))


def round_trips(
    symbol: Symbol, to_data: Callable[[Symbol], dict[str, Any]] = symbol_to_data
) -> bool:
    """Return whether reading the resolved data of a symbol gives the normalised symbol back."""
    return symbol_from_data(to_data(symbol)) == normalised(symbol)
