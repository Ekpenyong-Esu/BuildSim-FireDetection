"""HTTP adapter for BuildSim. The only package that knows BuildSim exists.

`transport.py` is how we talk, `client.py` is what we say, `viewer.py` is the
one part that remembers anything.
"""

from .client import BuildSim
from .transport import BuildSimError
from .viewer import ViewerSessions

__all__ = ["BuildSim", "BuildSimError", "ViewerSessions"]
