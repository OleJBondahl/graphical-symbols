# graphical-symbols: agent guide

Standard-agnostic Python toolkit for graphical-symbol data. It reads TOML symbol files, resolves
composition, lints the wiring contract, renders SVG, and builds a resolved JSON bundle plus an SVG
gallery. Data packages hold only data and reuse this toolkit: `electrical-symbols` (a package
of the Schematika v2 monorepo, `../Schematika-v2`) now, ISO 14617 and ISA 5.1 later. Alpha,
single owner.

Schematika v2 consumes this repo by an exact git tag (its decision 0015): `electrical-symbols`,
`schematika-layout` and `schematika-render` import it. A change Schematika needs lands here
first, green and tagged `vX.Y.Z`, then Schematika bumps its pin. So a breaking change to a public
name is a coordinated change: it is released under a new tag, and the pin bump in Schematika v2
carries the matching edit there. Nothing in this repo may import or name a Schematika package.

## The guide decides

`src/graphical_symbols/docs/SYMBOL_INTERFACE.html` is the only design document (it ships as package
data, readable at runtime through `importlib.resources`; `electrical-symbols`' verbatim gate
reads it from the installed distribution, D38). It is final and binding. Read all of it before
doing anything. Never edit it. Definitions in it
(extents, overlap, orientations, the wire lane, placement, `repeat`, the 33 lint rules, the JSON
output format) are exact: implement them as written. The toolkit has one rule beyond the guide's
33, `lead-off-port` (D40).

Where the guide is silent, decide yourself and record the decision in `docs/DECISIONS.md`, one entry
each: what you decided, why, what it costs if wrong. If you believe the guide is wrong or
self-contradictory, do not edit it: implement it as written, record the concern in
`docs/DECISIONS.md` and report it to the owner at the end.

## The work

The toolkit the guide describes is built (guide sections 4 to 12). Work now arrives as a work
order from the Schematika workflow's orchestrator: a change a Schematika package needs, a
bug, or a new public function, each recorded in `docs/DECISIONS.md` (D38 and D39 are the
latest examples). Keep the public names of guide section 11 exactly as written; a new name gets
a decision entry.

## Rules

- Python 3.15 (`.python-version`), `uv` only (never bare `python` or `pip`), ruff, ty, pytest, hypothesis,
  vulture, deal. Every dependency pinned to the exact latest stable version. Runtime dependency:
  `deal` only (`jsonschema` may be a dev dependency for the agreement test). TOML is read with the
  standard library's `tomllib`.
- Pure core: every module-level function in a pure module is `@deal.pure` and does not raise. Only
  the modules that read or write files are impure. `scripts/fp_purity_gate.py` enforces it.
- `docs/` holds the guide's decisions (`DECISIONS.md`) only; plans stay out of the repo.
- Frozen slotted dataclasses; transforms are free functions; no positional port aliases.
- Every gate and lint rule is proven able to fail with a deliberately broken fixture.
- `just ci` passes before every commit; quote its output. Look at rendered output: convert SVGs to
  PNG and view them (`uv run --with cairosvg` or playwright, from a scratch directory outside
  the repo).
- Git: stage named paths only; Conventional Commits ending with
  the attribution line your session gives; work on a feature branch from `main`, never commit to
  `main` directly. The orchestrator reviews, merges, pushes and tags the release (`vX.Y.Z`,
  matching `version` in `pyproject.toml`); an implementer does not.
- Never edit another repo. A change Schematika v2 needs because of yours goes in your hand-back.

## Done means

The work order's acceptance is met, every new rule or gate has a failing fixture, `just ci` is
green (quote it), and the hand-back lists every decision recorded and anything the owner must
decide.
