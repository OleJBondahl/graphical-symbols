"""The design guide ships as package data, readable from an installed distribution (D38).

`electrical-symbols`' verbatim gate reads this resource, not a sibling checkout path, so this
package must resolve it through `importlib.resources` regardless of whether it is installed from
a source checkout, a git dependency or a built wheel.
"""

import importlib.resources

GUIDE_TITLE = "<title>Symbol interface design guide</title>"


def test_the_guide_resolves_as_package_data():
    resource = importlib.resources.files("graphical_symbols").joinpath("docs/SYMBOL_INTERFACE.html")
    assert resource.is_file()
    text = resource.read_text(encoding="utf-8")
    assert GUIDE_TITLE in text


def test_the_check_can_fail():
    # A resource at the right path but the wrong content would not carry the guide's own title.
    assert GUIDE_TITLE not in "<title>Not the guide</title>"
