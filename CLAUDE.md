# graphical-symbols: agent guide

Standard-agnostic Python toolkit for graphical-symbol data. It reads TOML symbol files, resolves
composition, lints the wiring contract, renders SVG, and builds a resolved JSON bundle plus an SVG
gallery. Data repos hold only data and reuse this toolkit: `../iec60617` now, ISO 14617 and
ISA 5.1 later. Schematika (`../Schematika`) will be rewritten later to consume these repos; it is
read-only reference and never a constraint. Alpha, single owner, breaking changes are fine.

## The guide decides

`docs/SYMBOL_INTERFACE.html` is the only design document. It is final and binding. An identical copy
lives in `../iec60617`. Read all of it before doing anything. Never edit it. Definitions in it
(extents, overlap, orientations, the wire lane, placement, `repeat`, the 33 lint rules, the JSON
output format) are exact: implement them as written.

Where the guide is silent, decide yourself and record the decision in `docs/DECISIONS.md`, one entry
each: what you decided, why, what it costs if wrong. If you believe the guide is wrong or
self-contradictory, do not edit it: implement it as written, record the concern in
`docs/DECISIONS.md` and report it to the owner at the end.

## The work

Build the toolkit the guide describes (its sections 4 to 12), reworking the existing code as
section 13 says. In outline:

- The data model and geometry (section 11), `orient` in 8 orientations plus `translate`, the
  body, keepout and slot boxes, `repeat`.
- Reading: `library.toml`, TOML symbol files, structural validation, the published JSON Schema
  (`schema/symbol.schema.json`) and a fixture-driven test that it agrees with the Python reader.
- The resolver: composition by parts and anchors, inheritance rules, `Library`, `load_library`,
  `load_bundle`.
- The linter: all 33 rules, geometric ones in all 8 orientations, exemptions via `lint_allow`.
- SVG rendering: plain, and annotated (grid, ports with ids and lanes, anchors, slot boxes, both
  boxes), sample texts in slots.
- The build: resolved JSON per symbol, the bundle in `src/<package>/bundle.json`, SVGs, annotated
  SVGs, a gallery README, `write_build` and `stale_build`.
- Gates (section 12): every lint rule has a deliberately broken fixture that makes it fire; `orient`
  round-trips (property test); the guide's five examples load and lint clean and are the first test
  fixtures; the schema and the Python reader agree.

The order and the task breakdown are yours. `../iec60617` is built in parallel by another session
and needs the toolkit's `load_library`, `lint`, `repeat`, `write_build` and `stale_build`. Keep the
public names in guide section 11 exactly as written, and land the pieces `iec60617` needs (reading,
resolving, linting, building) before the polish.

## State of the code

`main` holds one commit; the earlier history was squashed on purpose. It contains an early
implementation of an older Python-factory design: `units`, `geometry`, `symbol` (with `bbox`),
`transform`, `svg`; 74 tests, 100% coverage, `just ci` green. Guide section 13 says what to keep,
rework and never build. Treat that code as raw material, not as a design.

## How to work

- Write your own plan and keep it under `.superpowers/` (git-ignored). Do not commit plans;
  `docs/` holds the guide and `DECISIONS.md` only.
- Execute with `superpowers:subagent-driven-development`: a fresh implementer subagent per task,
  a task review (spec and quality) after each, fix rounds by resuming the implementer, and a broad
  final review by the most capable model. Give each subagent the guide sections it needs and tell
  it to read them.
- Do not stop to ask between tasks. Decide, record, continue. Stop only for something irreversible,
  security-sensitive, outside these repos (a merge, a push, a publish), or a situation where every
  path forward is a guess.

## Rules

- Python 3.14, `uv` only (never bare `python`, `pip`, `python -c`), ruff, ty, pytest, hypothesis,
  vulture, deal. Every dependency pinned to the exact latest stable version. Runtime dependency:
  `deal` only (`jsonschema` may be a dev dependency for the agreement test). TOML is read with the
  standard library's `tomllib`.
- Pure core: every module-level function in a pure module is `@deal.pure` and does not raise. Only
  the modules that read or write files are impure. `scripts/fp_purity_gate.py` enforces it.
- Frozen slotted dataclasses; transforms are free functions; no positional port aliases.
- Every gate and lint rule is proven able to fail with a deliberately broken fixture.
- `just ci` passes before every commit; quote its output. Look at rendered output: convert SVGs to
  PNG and view them (Schematika's `pid_review.py` has a viewport bug; use `uv run --with cairosvg`
  or playwright from a scratch directory outside the repos).
- Git: stage named paths only; Conventional Commits ending with
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`; create a feature branch from `main`
  (for example `feat/build`) and work there; never commit to `main`; do not merge, push or publish.
- Never touch `../Schematika`, `../auxillary_cabinet_v3`, `../Juicebox` or `../iec60617`. Requests
  for `iec60617` go in your final report.

## Done means

Everything in "The work" is implemented and committed, reviews are clean, `just ci` is green (quote
it), and your final message lists every decision you made, every concern about the guide, and
anything the owner must decide.
