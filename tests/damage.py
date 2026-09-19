"""Shared by the damaged-file tests: hostile values, and a way to damage a decoded document."""

import copy
import math

from hypothesis import strategies as st

ODD_VALUES = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(-3, 3),
    st.floats(width=16).map(float),
    st.sampled_from(
        [1e6, -1e6, 1_000_001, -1_000_001, 1e7, math.nan, math.inf, -math.inf, 10**400, -(10**400)]
    ),
    st.sampled_from([0.0, 1.0, 8.0, 8.5, -0.5]),
    st.text(max_size=4),
    st.sampled_from(["N", "E", "R90", "thick", "dashed", "solid", "symbol", "mechanical_link"]),
    st.lists(st.integers(-2, 2), max_size=3),
    st.lists(st.lists(st.integers(-2, 2), max_size=3), max_size=3),
    st.dictionaries(st.sampled_from(["line", "at", "r", "id", "x"]), st.integers(0, 2), max_size=2),
)
# Integers past Python's 4300-digit str limit: repr() of one raises ValueError. jsonschema itself
# formats them into its error messages, so only the totality test below uses them.
HUGE_INTEGERS = st.integers(min_value=10**4301, max_value=10**4310) | st.integers(
    min_value=-(10**4310), max_value=-(10**4301)
)


def walk(node: object, path: tuple = ()) -> list[tuple]:
    """Every path to a value inside a decoded document, the root excluded."""
    found = []
    if isinstance(node, dict):
        items = list(node.items())
    elif isinstance(node, list):
        items = list(enumerate(node))
    else:
        return found
    for key, child in items:
        found.append((*path, key))
        found += walk(child, (*path, key))
    return found


def damage(base, pick, action, value, key):
    """Return a copy of `base` with one value replaced, deleted, or added at a chosen place."""
    data = copy.deepcopy(base)
    paths = walk(data)
    path = paths[pick % len(paths)]
    parent = data
    for step in path[:-1]:
        parent = parent[step]
    if action == "replace":
        parent[path[-1]] = value
    elif action == "delete":
        del parent[path[-1]]
    else:
        target = parent[path[-1]]
        if isinstance(target, dict):
            target[key] = value
        elif isinstance(target, list):
            target.append(value)
    return data
