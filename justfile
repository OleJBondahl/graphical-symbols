# symdef task runner
# Usage: just <target>

default:
    @just --list

# lint, format check and types
check:
    uv run ruff check src tests scripts
    uv run ruff format --check src tests scripts
    uv run ty check

# dead code sweep (confidence 60)
dead-code:
    uv run vulture src --min-confidence 60

# every pure module passes the stdlib-ast purity gate (scripts/fp_purity_gate.py)
purity:
    uv run python scripts/fp_purity_gate.py

# pytest with coverage; symdef must stay at 100 percent (--cov-fail-under=100 is
# baked into [tool.pytest.ini_options] addopts)
cov:
    uv run pytest --cov-report=term-missing

# the tests on Python 3.14, the oldest supported version (requires-python), in a throwaway env
test314:
    uv run --python 3.14 --isolated pytest --no-cov -q -p no:cacheprovider

ci: check dead-code purity cov test314

# build the docs site into .site/ (Zensical, strict: a broken link fails)
site:
    uv run python scripts/build_site.py

fmt:
    uv run ruff format src tests scripts
    uv run ruff check --fix src tests scripts

# a coverage-free run: addopts bakes --cov-fail-under=100 into a plain `pytest`, so a partial
# or ad-hoc run wants --no-cov
test:
    uv run pytest --no-cov
