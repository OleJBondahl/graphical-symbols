"""Module unit and grid constants, with snapping to the grid."""

import deal

DEFAULT_MODULE_MM: float = 2.5
GRID_DIVISION: float = 0.125


@deal.pure
def snap(v: float) -> float:
    """Round a value in module units to the nearest grid division (`GRID_DIVISION`, 0.125 M)."""
    return round(v / GRID_DIVISION) * GRID_DIVISION


@deal.pure
def on_grid(v: float, tol: float = 1e-9) -> bool:
    """Return whether a value in module units is within `tol` of a grid division."""
    return abs(v - snap(v)) <= tol
