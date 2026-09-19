"""Reading a bundle: `library_from_bundle`, `validate_bundle`, `parse_json` and `load_bundle`."""

import json
from pathlib import Path

from roundtrip import normalised

from graphical_symbols.build import load_library
from graphical_symbols.load import library_from_bundle
from graphical_symbols.model import Library
from graphical_symbols.serialize import bundle_to_data, to_json

GUIDE = Path(__file__).resolve().parent / "fixtures" / "guide"
LIBRARY = load_library(GUIDE)


def bundle_data() -> dict:
    """A fresh, mutable bundle of the guide library, as decoded JSON."""
    return json.loads(to_json(bundle_to_data(LIBRARY)))


class TestLibraryFromBundle:
    def test_it_gives_a_bare_library_of_the_same_symbols(self):
        library = library_from_bundle(bundle_data())
        assert isinstance(library, Library)
        assert (library.standard, library.title, library.number_pattern) == (
            "IEC 60617",
            "IEC 60617",
            "",
        )
        assert sorted(library.symbols) == sorted(LIBRARY.symbols)
        for number, symbol in LIBRARY.symbols.items():
            assert library.symbols[number] == normalised(symbol)

    def test_iteration_is_sorted_by_number(self):
        library = library_from_bundle(bundle_data())
        assert [s.reference.number for s in library] == sorted(LIBRARY.symbols)
