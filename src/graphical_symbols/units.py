"""Module unit and grid constants, with snapping to the grid."""

import deal

DEFAULT_MODULE_MM: float = 2.5
GRID_DIVISION: float = 0.125


@deal.pure
def snap(v: float) -> float:
    """Round a value to the nearest grid division."""
    return round(v / GRID_DIVISION) * GRID_DIVISION


@deal.pure
def on_grid(v: float, tol: float = 1e-9) -> bool:
    """Return whether a value is within tol of the grid."""
    return abs(v - snap(v)) <= tol
