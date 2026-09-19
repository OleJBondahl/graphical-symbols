# graphical-symbols task runner
# Usage: just <target>

default:
    @just --list

# apply formatting
format:
    uv run ruff format src tests scripts

# lint, format check and types
check:
    uv run ruff format --check src tests scripts
    uv run ruff check src tests scripts
    uv run ty check

test:
    uv run pytest

# every module-level def in a pure module carries @deal.pure
purity:
    uv run python scripts/fp_purity_gate.py

# dead code sweep (confidence 60)
dead-code:
    uv run vulture src --min-confidence 60

# full local CI: format check, ruff, ty, vulture, purity gate, pytest
ci: check dead-code purity test
