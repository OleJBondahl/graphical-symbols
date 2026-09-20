"""Domain errors."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graphical_symbols.model import Finding


class GraphicalSymbolsError(Exception):
    """Base class for every error this package raises."""


class UnknownSymbolError(GraphicalSymbolsError):
    """A library lookup found no symbol with the requested reference number."""


class LibraryError(GraphicalSymbolsError):
    """A library failed to load; `findings` says why."""

    def __init__(self, findings: tuple[Finding, ...]) -> None:
        """Keep the findings and summarise them in the message."""
        super().__init__("; ".join(f"{f.rule}: {f.message}" for f in findings))
        self.findings = findings
