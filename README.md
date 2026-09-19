# graphical-symbols

Standard-agnostic toolkit for graphical-symbol data. Symbols are TOML files; the toolkit loads
them, resolves composition, lints the wiring contract, renders SVG, and builds a resolved JSON
bundle plus a gallery. Standard repos such as [`iec60617`](../iec60617) hold only data and reuse
the toolkit and its gates. Later: ISO 14617 and ISA 5.1.

Status: alpha. The toolkit the guide describes is built: reading, resolving, linting, SVG and the
build, with every lint rule and gate proven by a failing fixture. Nothing is released.

## The design

[docs/SYMBOL_INTERFACE.html](docs/SYMBOL_INTERFACE.html) is the binding, final spec. Open it in a
browser. The key ideas:

- A symbol is a definition: no tag, terminal numbers, position or orientation. Those belong to
  the placement in a drawing library.
- Port ids are roles (`in`, `out`, `anode`, ...), never terminal markings (`13`, `A1`).
- Electrical function is data: nodes and typed paths, so a consumer can netlist without
  per-symbol knowledge.
- Text lives in slots: the symbol reserves boxes for tags and terminal markings.
- Module units (M = 2.5 mm), a 0.125 M drawing grid and a 1 M wiring grid. A strict wiring
  contract is linted in all 8 orientations.
- Composition mirrors the standard: composites reference parts by anchor, no copied coordinates.

## What is here

The data model and `orient`, the boxes and `repeat`, the TOML reader with its JSON Schema
(`schema/symbol.schema.json`), the composition resolver, 33 lint rules, plain and annotated SVG,
and the build (resolved JSON per symbol, the bundle, SVGs, a gallery README). Decisions the guide
leaves open, and concerns about the guide, are in [docs/DECISIONS.md](docs/DECISIONS.md).

## Use

A data repo has `library.toml` and `symbols/<number>.toml`; `root` below is its directory.

```python
from graphical_symbols import lint, load_library

library = load_library(root)  # raises LibraryError, listing every problem in the files
contact = library.get("S00227")  # by number; iterating a library is sorted by number
for finding in lint(contact):  # all 33 rules, geometric ones in all 8 orientations
    print(finding.rule, finding.location, finding.message)
```

Symbols are immutable; `orient`, `translate` and `repeat` return new ones. A repeated symbol is
an ordinary symbol with ports such as `1.in` and `3.out`.

```python
from graphical_symbols import Orientation, keepout_box, orient, repeat, to_svg

breaker = orient(repeat(contact, 3), Orientation.R0)
print(keepout_box(breaker))
svg = to_svg(breaker, annotate=True, texts={"tag": "-Q1"})
```

`write_build` writes `build/` and `src/<package>/bundle.json` under the repo; `stale_build` lists
the files that differ from what it would write, so a test can fail when a committed build is out
of date. `load_bundle` reads a bundle back without the sources.

```python
from graphical_symbols import load_bundle, stale_build, write_build

write_build(library, root)
assert stale_build(library, root) == ()
assert len(load_bundle(root / "src" / "iec60617" / "bundle.json")) == len(library)
```

## Development

```
uv sync
just ci        # format check, ruff, ty, vulture, purity gate, pytest with coverage
```

`tests/test_readme.py` runs the examples above, so they stay true. Agents: read
[CLAUDE.md](CLAUDE.md) first.
