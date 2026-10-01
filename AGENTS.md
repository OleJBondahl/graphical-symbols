# AGENTS.md

How an agent works in this repo. `CLAUDE.md` is the full rule set and wins on any conflict; this is
the short version.

graphical-symbols is a standard-agnostic Python toolkit for graphical-symbol data: it reads TOML
symbols, resolves composition, lints the wiring contract, renders SVG and builds a resolved JSON
bundle. Data packages hold only data. Consumers pin it by exact git tag. Concepts and calls:
[docs/GUIDE.md](docs/GUIDE.md).

## Commands

```bash
uv sync
just ci          # check, dead-code, purity, cov: the gate, run before every commit
just check       # ruff check, ruff format --check, ty check
just dead-code   # vulture, confidence 60
just purity      # scripts/fp_purity_gate.py
just cov         # pytest with coverage
just test        # pytest --no-cov, for a partial or ad-hoc run
just fmt         # ruff format and ruff check --fix
```

Coverage must stay at 100%, baked into `addopts`, so a partial pytest run fails on coverage alone:
use `just test` or `--no-cov`. Use `uv run` for everything; never bare `python` or `pip`.

## Rules (see CLAUDE.md)

- `src/graphical_symbols/docs/SYMBOL_INTERFACE.html` is binding and never edited. Read it first.
  Where it is silent, add one entry to `docs/DECISIONS.md` (what, why, cost if wrong). A concern
  about the spec is recorded there too, not fixed in the spec.
- Pure core: every module-level function in a pure module is `@deal.pure` and does not raise.
  Only `build.py` and `__init__.py` are impure; the purity gate enforces it.
- Dependencies are exact pins at the latest stable. No new dependency (`deal` is the one runtime
  dependency). Standard library `tomllib` reads TOML.
- Every lint rule and gate gets a deliberately failing fixture proving it can fail.
- Public names follow spec section 11; a new public name needs a decision entry.
- Nothing in the repo imports or names a Schematika package. Never edit another repo.
- Git: stage named paths, never `git add -A`; Conventional Commits; work on a branch from `main`,
  never commit to `main`. Implementers do not tag or push releases; the orchestrator does.
- `docs/` holds `DECISIONS.md` and `GUIDE.md` only; plans stay out of the repo.

## Where things live (`src/graphical_symbols/`)

- `model.py`, `geometry.py`, `units.py`, `errors.py`: dataclasses, enums, points, boxes, grid.
- `load.py`: TOML parsing and structural validation (pure). `schema/symbol.schema.json` is the
  JSON Schema.
- `resolve.py`: composition, `parts` and inheritance. `repeat.py`, `orient.py`, `boxes.py`.
- `lint/`: `registry.py` (the 34 rules), one module per rule group, `__init__.py` (`lint`).
- `svg.py`, `gallery.py`: rendering and the build's README.
- `serialize.py`: resolved JSON, bundle data and `build_files` (pure).
- `build.py`: the file I/O: `load_library`, `load_bundle`, `write_build`, `stale_build`.
- `_version.py`: written by `scripts/build.py` from `pyproject.toml`; do not edit it.
- Tests are in `tests/`; the sample library is `tests/fixtures/guide/`.

Done means the work order's acceptance is met and `just ci` is green with its output quoted.
