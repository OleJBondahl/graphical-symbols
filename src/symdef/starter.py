"""The starter set `symdef init` writes: one library and one symbol, made here so they cannot drift.

The texts are plain strings. `tests/test_project.py` loads, lints and builds them, so a change to
the format that breaks the starter fails a test.
"""

import deal

LIBRARY_TOML = """\
#:schema https://olejbondahl.github.io/symdef/symbol.schema.json
standard = "My symbols"
title = "My symbols"
number_pattern = '^[a-z][a-z0-9-]*$'

[vocabulary]
path_kinds = ["conductor", "impedance"]
potentials = []
links = []

[rules]
required_slots = ["tag", "marking.<port>"]
"""

SYMBOL_TOML = """\
#:schema https://olejbondahl.github.io/symdef/symbol.schema.json
schema = 1
name = "Resistor"
kind = "symbol"
status = "unverified"
reference = { standard = "My symbols", number = "resistor" }

ports = [
  { id = "in",  at = [0, -2], dir = "N" },
  { id = "out", at = [0, 2],  dir = "S" },
]

paths = [
  { from = "in", to = "out", kind = "impedance", through = true },
]

elements = [
  { line = [[0, -2], [0, -1]] },
  { line = [[0, 2], [0, 1]] },
  { polyline = [[-0.5, -1], [0.5, -1], [0.5, 1], [-0.5, 1]], closed = true },
]

[slots]
tag           = { at = [-1, 0],      side = "W", box = [6, 1] }
"marking.in"  = { at = [0.75, -1.5], side = "E", box = [1.5, 1] }
"marking.out" = { at = [0.75, 1.5],  side = "E", box = [1.5, 1] }
"""

GITATTRIBUTES = "* text=auto eol=lf\n"

# Path relative to the set's folder -> file text.
STARTER_FILES = {
    "library.toml": LIBRARY_TOML,
    "symbols/resistor.toml": SYMBOL_TOML,
    ".gitattributes": GITATTRIBUTES,
}


@deal.pure
def starter_files() -> dict[str, str]:
    """Return the starter set: each path relative to the set's folder, and its text."""
    return dict(STARTER_FILES)
