"""Build the JSON the UI reads. Reads engine state, never changes it.

One module per section of the snapshot, so a change to the room table cannot
disturb the life-safety numbers.
"""

from .builder import build
from .explain import why
from .spaces import rooms

__all__ = ["build", "rooms", "why"]
