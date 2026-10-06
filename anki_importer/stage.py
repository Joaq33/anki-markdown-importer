"""Which pass of an import we are in, and what the user is told about it."""

from enum import Enum


class Stage(Enum):
    """Where an import has got to. `message` is the line shown while here."""

    IDLE = "Nothing imported yet. Choose a folder and root notes, then run."
    DISCOVERING = "Looking through your notes..."
    DISCOVERED = "Found notes"
    IMPORTING = "Importing into Anki..."
    IMPORTED = "Imported"
    RESOLVING = "Resolving links between notes..."
    RESOLVED = "Links resolved"
    CANCELLED = "Stopped. The notes found so far are still here."

    def __init__(self, message: str) -> None:
        self.message = message
