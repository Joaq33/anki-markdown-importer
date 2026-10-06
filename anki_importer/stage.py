"""Which pass of an import we are in, and what the user is told about it."""

from enum import Enum


class Stage(Enum):
    """Where an import has got to."""

    IDLE = ("idle", "Nothing imported yet. Choose a folder and root notes, then run.")
    DISCOVERING = ("discovering", "Looking through your notes...")
    DISCOVERED = ("discovered", "Found no notes")
    IMPORTING = ("importing", "Importing into Anki...")
    IMPORTED = ("imported", "Nothing imported yet")
    RESOLVING = ("resolving", "Resolving links between notes...")
    RESOLVED = ("resolved", "Nothing imported yet")
    CANCELLED = ("cancelled", "Stopped. The notes found so far are still here.")
    DONE = ("done", "Done")

    def __init__(self, key: str, message: str) -> None:
        self.key = key
        self.message = message

    def with_count(self, count: int, noun: str = "note") -> str:
        """The message for this stage, with a count filled in."""
        if count == 0 and self is Stage.DISCOVERED:
            return "Found no notes to import"
        return f"{self.message} ({count} {noun}{'' if count == 1 else 's'})"

    def __str__(self) -> str:
        return self.key