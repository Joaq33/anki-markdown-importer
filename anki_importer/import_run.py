"""The import run: what happens between picking root notes and cards in Anki.

A run is driven in three passes, each of which yields events as it works so a
caller (the TUI, a test) can watch it and stop it:

1. `build_cards` walks the wiki-link graph and turns every note into a card.
2. `submit` sends those cards to Anki through a gateway.
3. `resolve_links` rewrites the link placeholders left by pass two, now that
   every target note has a real id.
"""

import re
import time
from dataclasses import dataclass
from threading import Event
from typing import Iterator

from .card import Card
from .card_builder import CardBuilder
from .gateway import AnkiGateway, LinkResolution, SubmitOutcome
from .stage import Stage
from .notes import FolderNoteSource, NoteDiscovery, NoteFound, NoteMissing, NoteSource


@dataclass(frozen=True)
class RunSettings:
    """Everything one import needs to know."""

    vault_path: str
    deck_name: str = "Default"
    root_notes: tuple[str, ...] = ()
    card_prefix: str = ""
    upsert: bool = False
    generate_links: bool = True
    # AnkiConnect does not like being hammered; a small pause per note is polite.
    throttle_seconds: float = 0.1


@dataclass(frozen=True)
class RunStarted:
    """The pass that follows is the one that decides what this run does."""

    stage: Stage


@dataclass(frozen=True)
class RunFinished:
    """The pass is done; how it went is in `stage` plus the run's own totals."""

    stage: Stage


@dataclass(frozen=True)
class NoteDiscovered:
    name: str


@dataclass(frozen=True)
class NoteUnreadable:
    name: str


@dataclass(frozen=True)
class CardBuilt:
    card: Card


@dataclass(frozen=True)
class CardSubmitted:
    front: str
    outcome: SubmitOutcome


@dataclass(frozen=True)
class RunSummary:
    added: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0

    @property
    def processed(self) -> int:
        return self.added + self.updated + self.skipped + self.failed


@dataclass(frozen=True)
class LinkProgress:
    resolved: int
    unresolved: int


@dataclass(frozen=True)
class LinksResolved:
    resolution: LinkResolution


BuildEvent = RunStarted | RunFinished | NoteDiscovered | NoteUnreadable | CardBuilt
SubmitEvent = CardSubmitted | RunSummary
LinkEvent = LinkProgress | LinksResolved

PENDING_LINK = re.compile(r"\[([^\]]*?)\|nidPENDING:([^\]]+)\]")


class ImportRun:
    """One import, from root notes to cards in Anki.

    Cancelling is cooperative: call `cancel` from another thread and the current
    pass stops at the next note, keeping whatever it has already done.
    """

    def __init__(
        self,
        settings: RunSettings,
        *,
        source: NoteSource | None = None,
        builder: CardBuilder | None = None,
        discovery: NoteDiscovery | None = None,
    ) -> None:
        self.settings = settings
        self._source: NoteSource = (
            source if source is not None else FolderNoteSource(settings.vault_path)
        )
        self._builder = builder if builder is not None else CardBuilder()
        self._discovery = (
            discovery if discovery is not None else NoteDiscovery(self._source)
        )
        self._cancelled = Event()
        self.cards: list[Card] = []
        self.missing: list[str] = []
        self.summary = RunSummary()
        self.links = LinkResolution()

    @property
    def discovery(self) -> NoteDiscovery:
        return self._discovery

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        """Ask the current pass to stop at the next note."""
        self._cancelled.set()

    def reset(self) -> None:
        """Forget the results of a previous pass, ready for a fresh run."""
        self._cancelled.clear()
        self.cards = []
        self.missing = []
        self.summary = RunSummary()
        self.links = LinkResolution()

    def build_cards(self) -> Iterator[BuildEvent]:
        """Walk the graph and build a card for every note it reaches."""
        yield RunStarted(Stage.DISCOVERING)
        for event in self._discovery.discover(self.settings.root_notes):
            if self.cancelled:
                return
            if isinstance(event, NoteMissing):
                self.missing.append(event.name)
                yield NoteUnreadable(event.name)
                continue

            found: NoteFound = event
            yield NoteDiscovered(found.name)
            card = self._builder.build(
                found.name,
                found.content,
                card_prefix=self.settings.card_prefix,
                generate_links=self.settings.generate_links,
            )
            self.cards.append(card)
            yield CardBuilt(card)
        yield RunFinished(Stage.DISCOVERED)

    def submit(self, gateway: AnkiGateway) -> Iterator[SubmitEvent]:
        """Send every card to Anki, honouring the skip flag and upsert."""
        added = updated = skipped = failed = 0
        for card in self.cards:
            if self.cancelled:
                break
            if card.should_skip:
                outcome = SubmitOutcome.SKIPPED
            elif self.settings.upsert:
                note_id = gateway.note_id_for_front(self.settings.deck_name, card.front)
                outcome = (
                    gateway.update_note(self.settings.deck_name, card, note_id)
                    if note_id is not None
                    else gateway.add_note(self.settings.deck_name, card)
                )
            else:
                outcome = gateway.add_note(self.settings.deck_name, card)

            if outcome is SubmitOutcome.ADDED:
                added += 1
            elif outcome is SubmitOutcome.UPDATED:
                updated += 1
            elif outcome is SubmitOutcome.SKIPPED:
                skipped += 1
            else:
                failed += 1
            self.summary = RunSummary(added, updated, skipped, failed)
            yield CardSubmitted(card.front, outcome)

            if self.settings.throttle_seconds:
                time.sleep(self.settings.throttle_seconds)

        self.summary = RunSummary(added, updated, skipped, failed)
        yield self.summary

    def resolve_links(self, gateway: AnkiGateway) -> Iterator[LinkEvent]:
        """Second pass: give every link placeholder the target note's real id."""
        if not self.settings.generate_links:
            return

        resolved = 0
        unresolved = 0
        unresolved_targets: list[str] = []

        for note_id in gateway.notes_with_pending_links(self.settings.deck_name):
            if self.cancelled:
                break
            back = gateway.note_back(note_id)
            if "nidPENDING" not in back:
                continue

            def rewrite(match: re.Match[str]) -> str:
                nonlocal resolved, unresolved
                alias, target = match.group(1), match.group(2)
                target_id = gateway.find_note_by_front(target)
                if target_id is not None:
                    resolved += 1
                    return f"[{alias}|nid{target_id}]"
                unresolved += 1
                if target not in unresolved_targets:
                    unresolved_targets.append(target)
                return alias

            replaced = PENDING_LINK.sub(rewrite, back)
            if replaced != back:
                gateway.replace_note_back(note_id, replaced)
            yield LinkProgress(resolved, unresolved)

        self.links = LinkResolution(resolved, unresolved, tuple(unresolved_targets))
        yield LinksResolved(self.links)


def parse_root_notes(text: str) -> tuple[str, ...]:
    """Root notes as typed by a user: comma or newline separated."""
    parts = text.replace("\n", ",").split(",")
    return tuple(part.strip() for part in parts if part.strip())