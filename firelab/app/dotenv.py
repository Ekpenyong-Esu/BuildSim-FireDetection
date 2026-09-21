"""Load `firelab/.env` into the environment, so secrets never have to be exported by hand.

One job: read KEY=VALUE lines from a file and set the ones that are not already
set. Variables exported in the shell win over the file. Nothing else in the
project reads the file; the LLM client still takes its settings from the
environment, which is the one place secrets are looked for.

The file is ignored by git. The names it may contain are LLM_BASE_URL, LLM_API_KEY,
LLM_MODEL and FIRELAB_DETECTOR; see the README.
"""

import os
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / ".env"  # firelab/.env


def load(path: Path = DEFAULT) -> list[str]:
    """Set every variable in `path` that the environment does not already have.

    Returns the names that were set, so the caller can say so in its log. Blank
    lines and `#` comments are skipped; a leading `export ` is allowed; values
    may be wrapped in single or double quotes.
    """
    if not path.is_file():
        return []
    loaded: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name and name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded
