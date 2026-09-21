"""Create the one Firelab engine used by the whole server.

It lives here rather than in `main` so the routers can import it without
importing the application that mounts them.
"""

from .config import Config
from .engine import Engine

engine = Engine(Config())
