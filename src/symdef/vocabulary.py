"""The vocabulary check: a symbol file may only use the words its `library.toml` declares."""

from collections.abc import Callable, Mapping
from typing import Any

from symdef.model import Finding, Severity, Vocabulary

# Where each word sits in a symbol file: the table array, the key, what to call the word, and
# the `[vocabulary]` list that declares it, by name and by getter.
_WORDS: tuple[tuple[str, str, str, str, Callable[[Vocabulary], tuple[str, ...]]], ...] = (
    ("paths", "kind", "path kind", "path_kinds", lambda v: v.path_kinds),
    ("nodes", "potential", "potential", "potentials", lambda v: v.potentials),
    ("parts", "via", "link", "links", lambda v: v.links),
)


def _line_of(word: str, text: str) -> int:
    """Return the 1-based first line of the text that quotes the word, or 1 if none does."""
    quoted = (f'"{word}"', f"'{word}'")
    return next(
        (n for n, line in enumerate(text.splitlines(), 1) if any(q in line for q in quoted)), 1
    )


def vocabulary_findings(
    data: Mapping[str, Any], vocabulary: Vocabulary, text: str
) -> tuple[Finding, ...]:
    """Report each word a symbol file uses that its set does not declare, once per word.

    Args:
        data: The decoded symbol file; entries of an unexpected shape are left to `validate`.
        vocabulary: The words the set declares.
        text: The file's text, to find the line of a word.

    Returns:
        One `schema` error per undeclared word, at the JSON-pointer-like place of its first use,
        naming the word and the line of the first line of `text` that quotes it.
    """
    found: dict[tuple[str, str], Finding] = {}
    for table, key, label, declared, words in _WORDS:
        entries = data.get(table)
        for index, entry in enumerate(entries if isinstance(entries, list) else ()):
            word = entry.get(key) if isinstance(entry, dict) else None
            if isinstance(word, str) and word not in words(vocabulary):
                message = (
                    f"{label} {word!r} is not declared in library.toml [vocabulary] {declared} "
                    f"(line {_line_of(word, text)})"
                )
                finding = Finding("schema", Severity.ERROR, message, f"/{table}/{index}/{key}")
                found.setdefault((label, word), finding)
    return tuple(found.values())
