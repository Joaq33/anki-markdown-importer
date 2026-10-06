"""Talking to Anki over AnkiConnect.

`AnkiGateway` is the one seam where this app talks to the outside world. Every
method is a single Anki operation, so a test substitutes one small object and
never has to reason about HTTP.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

import requests

from .card import Card

DEFAULT_HOST = "http://localhost"
DEFAULT_PORT = "8765"
DUPLICATE_ERROR = "cannot create note because it is a duplicate"


class SubmitOutcome(Enum):
    """What Anki did with a submitted card."""

    ADDED = "added"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class LinkResolution:
    """The result of the second pass that turns link placeholders into note ids."""

    resolved: int = 0
    unresolved: int = 0
    unresolved_targets: tuple[str, ...] = ()


class AnkiGateway(Protocol):
    """The Anki operations this app needs."""

    def is_available(self) -> bool:
        """Whether AnkiConnect answered."""

    def note_id_for_front(self, deck_name: str, front: str) -> int | None:
        """The id of the note in this deck whose front matches, if there is one."""

    def add_note(self, deck_name: str, card: Card) -> SubmitOutcome: ...

    def update_note(self, deck_name: str, card: Card, note_id: int) -> SubmitOutcome: ...

    def notes_with_pending_links(self, deck_name: str) -> list[int]:
        """Ids of every note in the deck still holding an unresolved link."""

    def note_back(self, note_id: int) -> str: ...

    def replace_note_back(self, note_id: int, back: str) -> bool: ...


class AnkiConnectGateway:
    """AnkiGateway over the AnkiConnect HTTP API."""

    def __init__(
        self, host: str = DEFAULT_HOST, port: str = DEFAULT_PORT, timeout: float = 5.0
    ) -> None:
        self.url = f"{host}:{port}"
        self.timeout = timeout

    def _call(self, action: str, **params: Any) -> Any:
        payload: dict[str, Any] = {"action": action, "version": 6}
        if params:
            payload["params"] = params
        response = requests.post(self.url, json=payload, timeout=self.timeout)
        return response.json()

    def is_available(self) -> bool:
        try:
            result = self._call("version")
        except (requests.exceptions.RequestException, ValueError):
            return False
        return isinstance(result, dict) and not result.get("error")

    def note_id_for_front(self, deck_name: str, front: str) -> int | None:
        try:
            result = self._call("findNotes", query=f'deck:"{deck_name}" front:"{front}"')
        except (requests.exceptions.RequestException, ValueError):
            return None
        found: Sequence[Any] = result.get("result") or []
        return int(found[0]) if found else None

    def add_note(self, deck_name: str, card: Card) -> SubmitOutcome:
        try:
            result = self._call(
                "addNote",
                note={
                    "deckName": deck_name,
                    "modelName": "Basic",
                    "fields": {"Front": card.front, "Back": card.back},
                    "tags": sorted(card.tags),
                },
            )
        except (requests.exceptions.RequestException, ValueError):
            return SubmitOutcome.FAILED
        error = result.get("error")
        if error:
            return (
                SubmitOutcome.SKIPPED if error == DUPLICATE_ERROR else SubmitOutcome.FAILED
            )
        return SubmitOutcome.ADDED

    def update_note(self, deck_name: str, card: Card, note_id: int) -> SubmitOutcome:
        try:
            result = self._call(
                "updateNote",
                note={
                    "id": note_id,
                    "deckName": deck_name,
                    "fields": {"Back": card.back},
                    "tags": sorted(card.tags),
                },
            )
        except (requests.exceptions.RequestException, ValueError):
            return SubmitOutcome.FAILED
        return SubmitOutcome.FAILED if result.get("error") else SubmitOutcome.UPDATED

    def notes_with_pending_links(self, deck_name: str) -> list[int]:
        try:
            result = self._call(
                "findNotes", query=f'deck:"{deck_name}" Back:*nidPENDING*'
            )
        except (requests.exceptions.RequestException, ValueError):
            return []
        return [int(note_id) for note_id in (result.get("result") or [])]

    def note_back(self, note_id: int) -> str:
        try:
            result = self._call("notesInfo", notes=[note_id])
        except (requests.exceptions.RequestException, ValueError):
            return ""
        notes: Sequence[Any] = result.get("result") or []
        if not notes:
            return ""
        return str(notes[0].get("fields", {}).get("Back", {}).get("value", ""))

    def replace_note_back(self, note_id: int, back: str) -> bool:
        """Overwrite just the back of a note. Used by link resolution."""
        try:
            result = self._call(
                "updateNote", note={"id": note_id, "fields": {"Back": back}}
            )
        except (requests.exceptions.RequestException, ValueError):
            return False
        return not result.get("error")