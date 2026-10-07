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

# every module-level def in a pure module carries @deal.pure
purity:
    uv run python scripts/fp_purity_gate.py

# pytest with coverage; symdef must stay at 100 percent (--cov-fail-under=100 is
# baked into [tool.pytest.ini_options] addopts)
cov:
    uv run pytest --cov-report=term-missing

ci: check dead-code purity cov

fmt:
    uv run ruff format src tests scripts
    uv run ruff check --fix src tests scripts

# a coverage-free run: addopts bakes --cov-fail-under=100 into a plain `pytest`, so a partial
# or ad-hoc run wants --no-cov
test:
    uv run pytest --no-cov
