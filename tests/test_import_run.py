"""Tests for the import run: discovery, building, submission, link resolution.

The AnkiConnect boundary is substituted with `FakeAnkiGateway`, so these run
with no Anki and no network.
"""

from dataclasses import dataclass, field

import pytest

from anki_importer.card import Card
from anki_importer.gateway import LinkResolution, SubmitOutcome
from anki_importer.import_run import (
    CardBuilt,
    CardSubmitted,
    LinksResolved,
    NoteUnreadable,
    RunSettings,
    RunSummary,
    ImportRun,
)
from anki_importer.notes import FolderNoteSource

LINKED_PAIR = {
    "root_note.md": "---\ntags: [root]\n---\n# Root\nSee [[linked_note]].\n",
    "linked_note.md": "---\ntags: [linked]\n---\n# Linked\nBack to [[root_note]].\n",
}


@dataclass
class FakeAnkiGateway:
    """An Anki that lives in memory."""

    deck_name: str = "Default"
    online: bool = True
    notes: dict[int, Card] = field(default_factory=dict)
    existing_fronts: dict[str, int] = field(default_factory=dict)
    reject: set[str] = field(default_factory=set)
    _next_id: int = 1000

    def is_available(self) -> bool:
        return self.online

    def note_id_for_front(self, deck_name: str, front: str) -> int | None:
        return self.existing_fronts.get(f"{deck_name}:{front}")

    def find_note_by_front(self, front: str) -> int | None:
        for key, note_id in self.existing_fronts.items():
            if key.split(":", 1)[1] == front:
                return note_id
        return None

    def add_note(self, deck_name: str, card: Card) -> SubmitOutcome:
        if card.front in self.reject:
            return SubmitOutcome.FAILED
        if f"{deck_name}:{card.front}" in self.existing_fronts:
            return SubmitOutcome.SKIPPED
        self._next_id += 1
        self.notes[self._next_id] = card
        self.existing_fronts[f"{deck_name}:{card.front}"] = self._next_id
        return SubmitOutcome.ADDED

    def update_note(self, deck_name: str, card: Card, note_id: int) -> SubmitOutcome:
        if card.front in self.reject:
            return SubmitOutcome.FAILED
        self.notes[note_id] = card
        self.existing_fronts[f"{deck_name}:{card.front}"] = note_id
        return SubmitOutcome.UPDATED

    def notes_with_pending_links(self, deck_name: str) -> list[int]:
        return [
            note_id
            for note_id, card in self.notes.items()
            if "nidPENDING" in card.back
        ]

    def note_back(self, note_id: int) -> str:
        return self.notes[note_id].back

    def replace_note_back(self, note_id: int, back: str) -> bool:
        card = self.notes[note_id]
        card.back = back
        return True


@pytest.fixture
def vault(tmp_path):
    for name, content in LINKED_PAIR.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    return tmp_path


def make_run(vault, **settings) -> ImportRun:
    return ImportRun(
        RunSettings(vault_path=str(vault), **settings),
        source=FolderNoteSource(vault),
    )


class TestBuildCards:
    def test_a_dry_run_builds_a_card_for_every_note_the_graph_reaches(self, vault):
        run = make_run(vault, root_notes=("root_note",))

        list(run.build_cards())

        assert sorted(card.front for card in run.cards) == ["linked_note", "root_note"]

    def test_a_dry_run_alone_never_contacts_anki(self, vault):
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",))

        list(run.build_cards())

        assert gateway.notes == {}
        assert run.summary.processed == 0

    def test_a_link_to_a_note_that_is_not_in_the_vault_is_reported(self, vault):
        (vault / "root_note.md").write_text("[[nowhere]]\n", encoding="utf-8")
        run = make_run(vault, root_notes=("root_note",))

        events = list(run.build_cards())

        assert any(isinstance(event, NoteUnreadable) for event in events)
        assert run.missing == ["nowhere"]

    def test_a_missing_note_does_not_stop_the_notes_around_it(self, vault):
        (vault / "root_note.md").write_text("[[nowhere]]\n[[linked_note]]\n", "utf-8")
        run = make_run(vault, root_notes=("root_note",))

        list(run.build_cards())

        assert [card.front for card in run.cards] == ["root_note", "linked_note"]
        assert run.missing == ["nowhere"]

    def test_building_reports_each_card_as_it_becomes_ready(self, vault):
        run = make_run(vault, root_notes=("root_note",))

        events = list(run.build_cards())

        assert sum(isinstance(event, CardBuilt) for event in events) == 2

    def test_a_note_tagged_not_included_is_built_but_marked_to_skip(self, vault):
        (vault / "root_note.md").write_text(
            "---\ntags: [not_included]\n---\nBody\n", encoding="utf-8"
        )
        run = make_run(vault, root_notes=("root_note",))

        list(run.build_cards())

        assert [card.should_skip for card in run.cards] == [True]


class TestSubmit:
    def test_importing_sends_every_note_to_the_chosen_deck(self, vault):
        gateway = FakeAnkiGateway(deck_name="Maths")
        run = make_run(vault, root_notes=("root_note",), deck_name="Maths")
        list(run.build_cards())

        list(run.submit(gateway))

        assert sorted(card.front for card in gateway.notes.values()) == [
            "linked_note",
            "root_note",
        ]

    def test_importing_reports_what_anki_did_with_each_note(self, vault):
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())

        events = list(run.submit(gateway))

        outcomes = {
            event.front: event.outcome
            for event in events
            if isinstance(event, CardSubmitted)
        }
        assert set(outcomes.values()) == {SubmitOutcome.ADDED}

    def test_with_upsert_an_existing_note_is_updated_rather_than_duplicated(self, vault):
        gateway = FakeAnkiGateway()
        gateway.existing_fronts["Default:root_note"] = 42
        gateway.notes[42] = Card(front="root_note", back="stale")
        run = make_run(vault, root_notes=("root_note",), upsert=True)
        list(run.build_cards())

        list(run.submit(gateway))

        assert gateway.notes[42].back != "stale"
        assert run.summary.updated == 1
        assert run.summary.added == 1

    def test_without_upsert_anki_rejects_the_duplicate_and_the_note_is_skipped(self, vault):
        gateway = FakeAnkiGateway()
        gateway.existing_fronts["Default:root_note"] = 42
        run = make_run(vault, root_notes=("root_note",), upsert=False)
        list(run.build_cards())

        list(run.submit(gateway))

        assert run.summary.skipped == 1
        assert run.summary.added == 1

    def test_a_note_marked_to_skip_is_never_sent_to_anki(self, vault):
        gateway = FakeAnkiGateway()
        (vault / "root_note.md").write_text(
            "---\ntags: [not_included]\n---\nBody\n", encoding="utf-8"
        )
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())

        list(run.submit(gateway))

        assert gateway.notes == {}

    def test_a_note_anki_rejects_is_counted_as_a_failure_and_the_run_continues(self, vault):
        gateway = FakeAnkiGateway(reject={"root_note"})
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())

        list(run.submit(gateway))

        assert run.summary.failed == 1
        assert run.summary.added == 1

    def test_the_summary_reports_the_whole_run(self, vault):
        gateway = FakeAnkiGateway(reject={"linked_note"})
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())

        events = list(run.submit(gateway))

        summary = next(event for event in events if isinstance(event, RunSummary))
        assert (summary.added, summary.failed) == (1, 1)

    def test_an_edit_made_after_building_is_what_gets_submitted(self, vault):
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())
        run.cards[0].front = "renamed"

        list(run.submit(gateway))

        assert "renamed" in {card.front for card in gateway.notes.values()}

    def test_cancelling_stops_the_import_and_counts_only_what_was_sent(self, vault):
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())

        run.cancel()
        list(run.submit(gateway))

        assert run.summary.processed == 0
        assert gateway.notes == {}
        assert run.cancelled is True

    def test_cancelling_half_way_counts_only_the_notes_already_sent(self, vault):
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())
        events = run.submit(gateway)
        next(events)  # the first note goes through

        run.cancel()
        list(events)

        assert run.summary.processed == 1


class TestLinkResolution:
    def test_placeholders_are_replaced_with_the_real_note_id(self, vault):
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",), generate_links=True)
        list(run.build_cards())
        list(run.submit(gateway))

        list(run.resolve_links(gateway))

        root = next(
            card for card in gateway.notes.values() if card.front == "root_note"
        )
        linked_id = gateway.existing_fronts["Default:linked_note"]
        assert f"[linked_note|nid{linked_id}]" in root.back

    def test_a_placeholder_whose_target_is_missing_becomes_plain_text_and_is_reported(
        self, vault
    ):
        (vault / "root_note.md").write_text("See [[linked_note]].\n", encoding="utf-8")
        (vault / "orphan_note.md").write_text("Points at [[nowhere]].\n", encoding="utf-8")
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())
        orphan = Card(front="orphan_note", back="Points at [nowhere|nidPENDING:nowhere].")
        gateway.notes[7] = orphan

        events = list(run.resolve_links(gateway))

        resolution = next(event for event in events if isinstance(event, LinksResolved))
        assert resolution.resolution.resolved == 0
        assert resolution.resolution.unresolved == 1
        assert resolution.resolution.unresolved_targets == ("nowhere",)
        assert gateway.note_back(7) == "Points at nowhere."

    def test_link_resolution_is_skipped_when_link_generation_is_off(self, vault):
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",), generate_links=False)
        list(run.build_cards())
        list(run.submit(gateway))

        events = list(run.resolve_links(gateway))

        assert not any(isinstance(event, LinksResolved) for event in events)

class TestResolveLinksParity:
    def test_resolution_finds_a_target_even_when_it_lives_in_another_deck(
        self, vault
    ):
        gateway = FakeAnkiGateway()
        run = make_run(vault, root_notes=("root_note",))
        list(run.build_cards())
        list(run.submit(gateway))
        gateway.existing_fronts.clear()
        gateway.existing_fronts["Other:linked_note"] = 555

        list(run.resolve_links(gateway))

        assert run.links.resolved == 1
        assert run.links.unresolved_targets == ("root_note",)
        root = next(
            card for card in gateway.notes.values() if card.front == "root_note"
        )
        assert "[linked_note|nid555]" in root.back
