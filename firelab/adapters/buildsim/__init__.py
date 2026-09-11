"""HTTP adapter for BuildSim. The only package that knows BuildSim exists.

`transport.py` is how we talk, `client.py` is what we say, `viewer.py` is the
one part that remembers anything.
"""

from .client import BuildSim
from .transport import BuildSimError
from .viewer import ViewerSessions

# BuildSim floor plans are drawn in units of 0.5 m.
UNITS_TO_METRES = 0.5

__all__ = ["UNITS_TO_METRES", "BuildSim", "BuildSimError", "ViewerSessions"]
