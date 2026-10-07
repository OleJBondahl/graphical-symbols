# symdef: agent guide

Standard-agnostic Python toolkit for graphical-symbol data. It reads TOML symbol files, resolves
composition, lints the wiring contract, renders SVG, and builds a resolved JSON bundle plus an SVG
gallery. Data packages hold only data and reuse this toolkit: `electrical-symbols` (a package
of the Fransys repo, `../fransys-dev`) now, ISO 14617 and ISA 5.1 later. Alpha,
single owner.

Fransys is
one user. It pins an exact PyPI version, and its `electrical-symbols` package is an IEC 60617
data package. A change Fransys needs lands here first, released as `vX.Y.Z` on PyPI, then
Fransys bumps its pin. No code, test or script here imports or names a Fransys package.

## The spec decides

`src/graphical_symbols/docs/SYMBOL_INTERFACE.html` (the spec; older entries in
`docs/DECISIONS.md` call it the guide) is the only design document. It ships as package data,
readable at runtime through `importlib.resources`; `electrical-symbols`' verbatim gate reads it
from the installed distribution (D38). It is final and binding. Read all of it before doing
anything. Never edit it. Definitions in it
(extents, overlap, orientations, the wire lane, placement, `repeat`, the 33 lint rules, the JSON
output format) are exact: implement them as written. The toolkit has one rule beyond the spec's
33, `lead-off-port` (D40).

Where the spec is silent, decide yourself and record the decision in `docs/DECISIONS.md`, one entry
each: what you decided, why, what it costs if wrong. If you believe the spec is wrong or
self-contradictory, do not edit it: implement it as written, record the concern in
`docs/DECISIONS.md` and report it to the owner at the end.

## The work

The toolkit the spec describes is built (spec sections 4 to 12). Work now arrives as a work
order from the Fransys workflow's orchestrator: a change a Fransys package needs, a
bug, or a new public function, each recorded in `docs/DECISIONS.md`. Keep the public names of
spec section 11 exactly as written; a new name gets a decision entry.

## Rules

- Python 3.15 (`.python-version`); `requires-python` is `>=3.14`, and `just
  ci` runs the tests on 3.14 too, `uv` only (never bare `python` or `pip`), ruff, ty, pytest, hypothesis,
  vulture. Every dependency pinned to the exact latest stable version. No runtime dependency
  (`jsonschema` may be a dev dependency for the agreement test). TOML is read with the
  standard library's `tomllib`.
- Pure core: every module under `src/symdef/` is pure except those listed in
  `scripts/fp_purity_gate.py`'s `IMPURE_MODULES`. A pure module does no file or console I/O, reads
  no clock or randomness, and writes no module or global state. A function raises only the errors
  its docstring names. The gate enforces it with the standard library's `ast`. No contract
  library: users pay for nothing they did not ask for (owner 2026-10-07).
- `docs/` holds `DECISIONS.md` and `GUIDE.md` only; plans stay out of the repo.
- Frozen slotted dataclasses; transforms are free functions; no positional port aliases.
- Every gate and lint rule is proven able to fail with a deliberately broken fixture.
- `just ci` passes before every commit; quote its output. Look at rendered output: convert SVGs to
  PNG and view them (`uv run --with cairosvg` or playwright, from a scratch directory outside
  the repo).
- Git: stage named paths only; Conventional Commits ending with
  the attribution line your session gives; work on a feature branch from `main`, never commit to
  `main` directly. The orchestrator reviews, merges, pushes and tags the release (`vX.Y.Z`,
  matching `version` in `pyproject.toml`); an implementer does not.
- Never edit another repo. A change Fransys needs because of yours goes in your hand-back.
- User-facing files (README.md, `docs/`, the package's docs and docstrings) name no user of the toolkit, Fransys included. They are complete on their own; the docs site holds everything a user needs (owner 2026-10-07).

## Done means

The work order's acceptance is met, every new rule or gate has a failing fixture, `just ci` is
green (quote it), and the hand-back lists every decision recorded and anything the owner must
decide.
