"""Build the read-only data that the browser displays.

One module per section of the snapshot, so a change to the room table cannot
disturb the life-safety numbers.
"""

from .builder import build
from .explain import why
from .spaces import rooms

__all__ = ["build", "rooms", "why"]
