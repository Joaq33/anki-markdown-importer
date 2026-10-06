"""Completing what you type: note names, one per comma-separated segment."""

from textual.suggester import Suggester


class NoteSuggester(Suggester):
    """Suggest note names, completing only the name being typed.

    The roots field holds several notes separated by commas, so the stock
    suggester (which completes the whole value) would clobber the rest. This
    one completes the segment after the last comma and leaves the rest, and
    the casing you typed, alone.
    """

    def __init__(self, notes: list[str]) -> None:
        # Case is handled inside get_suggestion so the head you typed keeps
        # the casing you gave it.
        super().__init__(case_sensitive=True, use_cache=False)
        self._notes = sorted(notes, key=str.casefold)

    async def get_suggestion(self, value: str) -> str | None:
        head, separator, tail = value.rpartition(",")
        needle = tail.strip().casefold()
        if not needle:
            return None
        for note in self._notes:
            if note.casefold().startswith(needle) and note.casefold() != needle:
                return f"{head}{separator} {note}" if separator else note
        return None