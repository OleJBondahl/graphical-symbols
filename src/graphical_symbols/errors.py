"""Domain errors."""


class GraphicalSymbolsError(Exception):
    """Base class for every error this package raises."""


class InvalidSymbolError(GraphicalSymbolsError):
    """A symbol violates a structural invariant."""


class DuplicateSymbolError(GraphicalSymbolsError):
    """A registry received two symbols with the same reference number."""


class UnknownSymbolError(GraphicalSymbolsError):
    """A registry lookup found no symbol with the requested reference number."""
