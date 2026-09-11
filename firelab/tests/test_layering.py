"""The layer rules the docstrings claim, checked instead of merely stated.

`domain/` says it is pure and `intelligence.py` says it never touches the truth.
Both were only ever promises in prose until this file existed.
"""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Everything a pure module is allowed to reach for: the standard library corners
# the physics and the scoring genuinely need, and nothing else.
ALLOWED_IMPORTS = {
    "collections",
    "dataclasses",
    "enum",
    "math",
    "random",
    "typing",
    "__future__",
}


def _imports(path: Path) -> set[str]:
    """Every top-level package name imported by one file, relative ones excluded."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _attributes(path: Path) -> set[str]:
    """Every attribute name read anywhere in one file, e.g. `x.smoke` -> "smoke"."""
    return {
        node.attr for node in ast.walk(ast.parse(path.read_text())) if isinstance(node, ast.Attribute)
    }


def _sources() -> list[Path]:
    """Our own modules. The virtualenv and the built UI are not ours to police."""
    return sorted(p for folder in ("app", "domain", "adapters") for p in (ROOT / folder).rglob("*.py"))


class TestLayering(unittest.TestCase):
    # domain/ must run anywhere: no network, no clock, no configuration.
    def test_domain_is_pure(self):
        for path in sorted((ROOT / "domain").glob("*.py")):
            with self.subTest(module=path.name):
                self.assertEqual(_imports(path) - ALLOWED_IMPORTS, set())

    # The INTELLIGENCE zone is handed readings. The truth is one attribute away
    # and must stay unread, which is the whole point of it being its own file.
    def test_intelligence_never_reads_the_truth(self):
        read = _attributes(ROOT / "app" / "engine" / "intelligence.py")
        self.assertEqual(read & {"temperature", "smoke", "co"}, set())

    # Only the adapters may speak HTTP, so nothing else may import the client.
    def test_only_adapters_talk_to_buildsim(self):
        for path in _sources():
            if "adapters" in path.parts:
                continue
            with self.subTest(module=str(path.relative_to(ROOT))):
                self.assertNotIn("httpx", _imports(path))


if __name__ == "__main__":
    unittest.main()
