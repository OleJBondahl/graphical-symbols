# Guide to symdef

For someone writing a symbol set or consuming the toolkit. It assumes no standard: your set names its own
words and rules. The examples use one set of IEC 60617 symbols, because that is what the test fixtures hold.
New here? Start with the [tutorial](TUTORIAL.md). The binding spec is
[SYMBOL_INTERFACE.html](../src/symdef/docs/SYMBOL_INTERFACE.html) (the "spec" below):
this guide names the concepts and the calls, and the spec has the exact definitions. Where the
spec was silent, the choice is a numbered entry in [DECISIONS.md](DECISIONS.md) (D1, D2, ...).

## Concepts

- **Symbol.** A definition, not a placement: no tag, terminal number, position or orientation.
  Those belong to the drawing program that places it. `Symbol` is a frozen dataclass; `orient`,
  `translate` and `repeat` return new ones. Spec sections 2 and 4.
- **Port.** A place where a wire may attach, with an id, a position and a direction. Ids are
  roles (`in`, `out`, `anode`), never terminal markings such as `13` or `A1`. Spec sections 3
  and 4.
- **Node.** A set of ports that are one electrical point. A port in no declared node gets a node
  of its own (`nodes_of`, in `model.py`). Spec section 5.
- **Path.** A typed link between two ports (`from`, `to`, a `kind` word and `through`). The kind is a string
  from your set's `[vocabulary]`, such as `switch_open` in the IEC fixtures. Paths are the function as data,
  so a consumer can read connectivity without knowing any symbol. Spec section 5.
- **Slot.** A box the symbol reserves for text: the `tag` and one `marking.<port>` per port. The
  box grows from the slot point towards its `side`. Spec section 6; `slot_box` returns it.
- **Anchor.** A named point with a direction where another symbol can attach, used by composites.
  Spec sections 4 and 7.
- **Composite.** A symbol made of `parts`, each a reference to another symbol, attached by
  anchor. It copies no coordinates and inherits ports, slots and elements from its parts (D20).
  Spec section 7.
- **Repeat.** `repeat(symbol, n)` makes an n-pole symbol from a one-pole one, stepping by
  `pole_pitch`. The result is an ordinary symbol with ports such as `1.in` and `3.out` (D16).
  Spec section 7.

Units are modules (1 M = `DEFAULT_MODULE_MM`, 2.5 mm) on a drawing grid of `GRID_DIVISION` (0.125) M;
wires run on a 1 M grid. The wiring contract is linted in all 8 orientations (`Orientation`).

## Layout of a symbol set

```
library.toml          standard, title, number_pattern, package (optional), vocabulary, rules
symbols/<number>.toml one file per symbol; the file stem is the reference number
build/                generated: resolved JSON, SVGs, a gallery README
src/<package>/bundle.json   generated: every symbol, resolved
```

`symdef init DIR` writes a starter set, `symdef build DIR` writes the generated files, and
`symdef check DIR` runs every gate a set needs (D48). Exit code 0 is done, 1 is problems found.

`library.toml` of the test fixture (`tests/fixtures/guide/`):

```toml
#:schema https://olejbondahl.github.io/symdef/symbol.schema.json
standard = "IEC 60617"
title = "IEC 60617 symbols"
number_pattern = '^S\d{5}$'

[vocabulary]
path_kinds = ["conductor", "switch_open", "switch_closed", "impedance", "source", "diode"]
potentials = ["earth", "protective_earth", "functional_earth", "frame"]
links = ["mechanical_link"]

[rules]
required_slots = ["tag", "marking.<port>"]
```

`[vocabulary]` lists the words a symbol may use as a path kind, a node potential or a `via` link.
The toolkit has no built-in list. A word not listed fails the load with the word, the file and the
line (D46). `required_slots` lists the slot ids every symbol must carry; `marking.<port>` means one per port.
Both tables are strict: an unknown key is a finding. The `#:schema` line lets an editor check the file as you type.

`src/<package>` is the standard lowercased with only letters and digits (`IEC 60617` gives
`iec60617`). An optional `package = "name"` line in `library.toml` names the folder instead (D45).

A reference number must be a file stem: letters, digits, `_` and `-` in parts joined by single
dots (D31). A set holds data only; the toolkit and its gates come from this package.

## Defining a symbol

This is `symbols/S00227.toml` of the same fixture, a make contact:

```toml
schema = 1
name = "Make contact, general symbol"
kind = "symbol"
status = "unverified"
reference = { standard = "IEC 60617", number = "S00227" }

ports = [
  { id = "in",  at = [0, -2], dir = "N" },
  { id = "out", at = [0, 2],  dir = "S" },
]

paths = [
  { from = "in", to = "out", kind = "switch_open", through = true },
]

anchors = [
  { id = "link", at = [-0.5, 0], dir = "W" },
]

elements = [
  { line = [[0, -2], [0, -1]] },
  { line = [[0, 2], [0, 1]] },
  { line = [[0, 1], [-1, -1]] },
]

[slots]
tag           = { at = [-1.5, 0],    side = "W", box = [6, 1] }
"marking.in"  = { at = [0.25, -1.5], side = "E", box = [1.5, 1] }
"marking.out" = { at = [0.25, 1.5],  side = "E", box = [1.5, 1] }
```

A composite lists `parts` and maps its own ports to theirs (`S00254.toml`, the push-button,
attaches an actuator to the contact's `link` anchor):

```toml
parts = [
  { as = "contact",  use = "S00227" },
  { as = "actuator", use = "S00171", attach = "link", to = "contact.link", length = 2, via = "mechanical_link" },
]

ports = { in = "contact.in", out = "contact.out" }
```

`src/symdef/schema/symbol.schema.json` ships in the wheel and carries the `$id`
`https://olejbondahl.github.io/symdef/symbol.schema.json`. It describes the file structurally only
(D4, D47): any string is a valid path kind there, and the declared words are a load check. The rules that need
meaning are lint rules. A line may bind to a port with `port`, and the file's `schema` integer
did not step for it (D40).

## Loading and resolving

```python
from symdef import load_library

library = load_library(root)    # root is the set's directory
contact = library.get("S00227")  # UnknownSymbolError if absent
```

`load_library` reads `library.toml` and every `symbols/*.toml`, validates each file, resolves
composition and returns a `Library`. A `Library` has `standard`, `title`, `number_pattern`,
`symbols`, `vocabulary` and `required_slots`; `len` and iteration work, and iteration is sorted by number. If any file has a
problem it raises `LibraryError` listing all of them, by file (D21). The pure core never raises:
problems are `Finding`s with the rule `schema` until `load_library` collects them (D3, D15).
Composite inheritance is D20; structural problems only the resolver sees are D17.

## Linting

```python
from symdef import lint
from symdef.lint import RULES

assert len(RULES) == 34
for finding in lint(contact, library.required_slots):
    print(finding.rule, finding.severity, finding.location, finding.orientation, finding.message)
```

There are 34 rules: the spec's 33 (section 9) and `lead-off-port`, the toolkit's one addition
(D40). `lint` takes a symbol in base orientation and your set's `required_slots`. That list is empty by default,
so no slot is required. It runs the orientation-dependent rules in all 8 itself (D6, D23, D46). It returns a tuple of `Finding`, each with `rule`, `severity` (`Severity`),
`message`, `location` (a string or `None`) and `orientation` (or `None`). They are ordered by the spec
table, then orientation, then location (D23, D34).

A symbol can exempt a rule with `lint_allow`, a list of `{ rule, reason }` (S00016, the
connection point, exempts three). `lint` removes the findings of the named rules, and reports
`allow-unknown` and `allow-unused` for exemptions that name no rule or never fire. The rules the
resolver reports cannot be exempted (C3). The spec's push-button example fails `pitch-overflow`
as written; see C1 in DECISIONS.md.

## Building

```python
from symdef import stale_build, write_build

write_build(library, root)
assert stale_build(library, root) == ()
```

`write_build` is what `symdef build` calls after loading and linting. It writes, under the set's `root`:

```
build/resolved/<number>.json   one resolved symbol (D11, D30)
build/svg/<number>.svg         plain
build/annotated/<number>.svg   ports, anchors, slots, lanes and sample texts (D33)
build/README.md                the gallery table
src/<package>/bundle.json      every symbol, resolved
```

`<package>` is the standard normalised to lowercase letters and digits (D8): `IEC 60617` gives
`iec60617`, and a standard with no letter or digit cannot be built (D35). Files are written as
bytes with LF endings and nothing is deleted. `stale_build` returns the files that are missing,
differ, or sit under `build/resolved`, `build/svg` or `build/annotated` without a symbol behind
them (D31). `symdef check` reports the same files as `stale-build`, so a committed build cannot go stale.
`scripts/build.py` in this repo is unrelated: it writes this package's `_version.py`.

## Serialized form

Resolved JSON has the symbol's fields with composition flattened and the `lint_allow` list kept
(D1, D11). The bundle is `{"schema": 1, "standard": ..., "symbols": {...}}` (D7).
`load_bundle(path)` reads a `bundle.json` back into a `Library` without the TOML sources; it
validates every symbol and requires the resolved form (D31). A package that ships a set
loads its bundle this way at import.

## Rendering

```python
from symdef import Orientation, orient, repeat, to_fragment, to_svg

breaker = orient(repeat(contact, 3), Orientation.R0)
svg = to_svg(breaker, annotate=True, texts={"tag": "-Q1"})
group = to_fragment(breaker)
```

`to_svg(symbol, *, module_mm=..., annotate=False, texts=None)` returns a standalone SVG document
whose viewBox is in module units. `annotate=True` adds the keep-out box, port labels, anchors,
slots and wire lanes; `texts` maps slot ids to sample text. `to_fragment(symbol)` returns a
placeable `<g>` fragment instead of a document (D39). Both are total: any input renders (D32).
`body_box`, `keepout_box` and `slot_box` give the boxes, and `on_grid` and `snap` the grid.

## Consuming

Install with `uv add symdef`, or pin the toolkit to an exact version from PyPI, never a range:

```toml
dependencies = ["symdef==X.Y.Z"]
```

Replace `X.Y.Z` with a released version. A change a consumer needs lands here first, is
released under a new tag, and the consumer then bumps its pin.
`LIBRARY_VERSION` is the installed version as a constant. The package has no runtime dependency
(D49). The spec ships as package data and is read through `importlib.resources` (D38).

## Where to read more

- The spec for exact definitions; DECISIONS.md for every choice the spec left open.
- `README.md` for the short tour, `CLAUDE.md` and `AGENTS.md` for how to work on the toolkit.
