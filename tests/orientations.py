"""The orientation that undoes another, for the tests: only R90 and R270 are not their own."""

from symdef.geometry import Orientation

_INVERSES = {Orientation.R90: Orientation.R270, Orientation.R270: Orientation.R90}


def inverse(orientation: Orientation) -> Orientation:
    """Return the orientation that undoes this one."""
    return _INVERSES.get(orientation, orientation)
