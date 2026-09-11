"""The one engine instance for the process. There is one building, so one simulation.

It lives here rather than in `main` so the routers can import it without
importing the application that mounts them.
"""

from .config import Config
from .engine import Engine

engine = Engine(Config())
