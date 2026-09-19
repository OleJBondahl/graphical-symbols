# graphical-symbols

Standard-agnostic toolkit for graphical-symbol data. Symbols are TOML files; the toolkit loads
them, resolves composition, lints the wiring contract, renders SVG, and builds a resolved JSON
bundle plus a gallery. Standard repos such as [`iec60617`](../iec60617) hold only data and reuse
the toolkit and its gates. Later: ISO 14617 and ISA 5.1.

Status: alpha, under construction. Nothing is released.

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

## The work

Implement the toolkit as the guide describes it: data model, `orient`, boxes, `repeat`, the TOML
reader and JSON Schema, the composition resolver, 33 lint rules (each with a failing fixture), SVG
rendering with slots and annotations, and the build outputs. The repo holds an early
implementation of an older design (units, geometry, `bbox`, `transform`, SVG) that the guide's
section 13 says how to rework.

## Development

```
uv sync
just ci        # format check, ruff, ty, vulture, purity gate, pytest with coverage
```

Agents: read [CLAUDE.md](CLAUDE.md) first.
