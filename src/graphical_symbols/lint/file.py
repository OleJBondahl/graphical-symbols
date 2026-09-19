"""File-group rules that read decoded file data: `metadata` and part ids for `id-format`."""

import re
from collections.abc import Mapping
from typing import Any

import deal

from graphical_symbols.lint.registry import quote, rule_finding
from graphical_symbols.model import Finding, LibraryConfig

_ID = re.compile(r"[a-z][a-z0-9_]*")


@deal.pure
def is_valid_id(text: str) -> bool:
    """Return whether a port, anchor or part id matches `^[a-z][a-z0-9_]*$` in full."""
    return _ID.fullmatch(text) is not None


@deal.pure
def _matches(pattern: str, text: str) -> bool:
    """Return whether the pattern is found in the text.

    `search`, not `fullmatch`: the pattern anchors itself with `^` and `$`, as the guide's example
    does. A pattern that does not compile matches nothing.
    """
    try:
        return re.search(pattern, text) is not None
    except re.error:
        return False


@deal.pure
def metadata_findings(
    stem: str, data: Mapping[str, Any], config: LibraryConfig
) -> tuple[Finding, ...]:
    """Check a validated file's identity: name, standard and number against the library.

    Args:
        stem: The file name without `.toml`.
        data: Decoded data for which `validate` returned no findings.
        config: The library's `library.toml`.

    Returns:
        A `metadata` finding for an empty name, a standard other than the config's, a number
        that does not match `number_pattern` and a number that differs from the stem.
    """
    found = []
    if not data["name"].strip():
        found.append(rule_finding("metadata", "the name is empty", "/name"))
    reference = data["reference"]
    if reference["standard"] != config.standard:
        found.append(
            rule_finding(
                "metadata",
                f"the standard {quote(reference['standard'])} differs from the library's "
                f"{quote(config.standard)}",
                "/reference/standard",
            )
        )
    number = reference["number"]
    if not _matches(config.number_pattern, number):
        found.append(
            rule_finding(
                "metadata",
                f"the number {quote(number)} does not match {quote(config.number_pattern)}",
                "/reference/number",
            )
        )
    if number != stem:
        found.append(
            rule_finding(
                "metadata",
                f"the number {quote(number)} differs from the file name {quote(stem)}",
                "/reference/number",
            )
        )
    return tuple(found)


@deal.pure
def part_id_findings(data: Mapping[str, Any]) -> tuple[Finding, ...]:
    """Return an `id-format` finding for every part id that is not a valid id."""
    return tuple(
        rule_finding(
            "id-format",
            f"the part id {quote(part['as'])} must match ^[a-z][a-z0-9_]*$",
            f"/parts/{index}/as",
        )
        for index, part in enumerate(data.get("parts", ()))
        if not is_valid_id(part["as"])
    )
