"""Create the one Firelab engine used by the whole server.

It lives here rather than in `main` so the routers can import it without
importing the application that mounts them.
"""

from . import dotenv
from .config import Config
from .engine import Engine

# firelab/.env, if there is one, before anything reads the environment. Shell
# variables still win; the file only fills in what is missing.
_loaded = dotenv.load()

engine = Engine(Config())
if _loaded:
    engine.log("info", "read from .env: " + ", ".join(_loaded))
