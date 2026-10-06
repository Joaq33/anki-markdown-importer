"""Characterisation tests for wiki-link discovery.

Expectations are literals observed from the importer before the prefactor.
"""

import pytest

from anki_importer.notes import (
    FolderNoteSource,
    NoteDiscovery,
    NoteFound,
    NoteMissing,
    list_note_names,
)

SAMPLE_NOTES = {
    "root_note.md": "---\ntags: [root]\n---\n# Root Note\n[[linked_note]]\n[[not_included_note]]\n",
    "linked_note.md": "---\ntags: [linked]\n---\n# Linked Note\n[[root_note]]\n",
    "not_included_note.md": "---\ntags: [not_included]\n---\n# Skipped\n",
}


@pytest.fixture
def vault(tmp_path):
    for name, content in SAMPLE_NOTES.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    return tmp_path


def names(events) -> list[str]:
    return [event.name for event in events]


class TestDiscovery:
    def test_discovery_follows_the_wiki_links_out_of_the_starting_notes(self, vault):
        discovery = NoteDiscovery(FolderNoteSource(vault))

        found = names(discovery.discover(["root_note"]))

        assert set(found) == {"root_note", "linked_note", "not_included_note"}

    def test_a_note_linked_to_from_several_notes_is_discovered_once(self, vault):
        discovery = NoteDiscovery(FolderNoteSource(vault))

        found = names(discovery.discover(["root_note", "linked_note"]))

        assert len(found) == len(set(found))

    def test_discovery_walks_the_graph_one_link_depth_at_a_time(self, tmp_path):
        (tmp_path / "depth0.md").write_text("[[depth1]]\n", encoding="utf-8")
        (tmp_path / "depth1.md").write_text("[[depth2]]\n", encoding="utf-8")
        (tmp_path / "depth2.md").write_text("no links\n", encoding="utf-8")
        discovery = NoteDiscovery(FolderNoteSource(tmp_path))

        found = names(discovery.discover(["depth0"]))

        assert found == ["depth0", "depth1", "depth2"]

    def test_a_link_to_a_note_that_does_not_exist_is_reported_as_missing(self, vault):
        (vault / "root_note.md").write_text("[[nowhere]]\n", encoding="utf-8")
        discovery = NoteDiscovery(FolderNoteSource(vault))

        events = list(discovery.discover(["root_note"]))

        assert names(events) == ["root_note", "nowhere"]
        assert isinstance(events[1], NoteMissing)

    def test_a_link_below_the_separator_is_still_followed(self, vault):
        (vault / "root_note.md").write_text(
            "Body\n\n---\n\nBelow the separator: [[linked_note]]\n", encoding="utf-8"
        )
        discovery = NoteDiscovery(FolderNoteSource(vault))

        found = names(discovery.discover(["root_note"]))

        assert "linked_note" in found

    def test_the_discovered_note_carries_its_content_so_it_is_only_read_once(self, vault):
        discovery = NoteDiscovery(FolderNoteSource(vault))

        events = list(discovery.discover(["root_note"]))

        first = events[0]
        assert isinstance(first, NoteFound)
        assert "Root Note" in first.content

    def test_discovery_tracks_every_note_it_has_seen(self, vault):
        discovery = NoteDiscovery(FolderNoteSource(vault))
        list(discovery.discover(["root_note"]))

        assert discovery.tracked == {"root_note", "linked_note", "not_included_note"}


class TestNoteSource:
    def test_a_note_is_found_whatever_the_case_of_its_name(self, vault):
        source = FolderNoteSource(vault)

        assert "Linked Note" in source.read("LINKED_NOTE")

    def test_reading_a_note_that_does_not_exist_raises(self, vault):
        source = FolderNoteSource(vault)

        with pytest.raises(FileNotFoundError):
            source.read("nowhere")

    def test_a_note_stored_with_the_markdown_extension_is_found_by_its_stem(self, tmp_path):
        (tmp_path / "Alpha.markdown").write_text("# Alpha\n", encoding="utf-8")
        source = FolderNoteSource(tmp_path)

        assert source.read("Alpha") == "# Alpha\n"

    def test_a_source_for_a_folder_that_does_not_exist_cannot_be_opened(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            FolderNoteSource(tmp_path / "nowhere")

class TestListingNotes:
    def test_listing_names_every_note_in_the_vault_by_its_stem(self, vault):
        assert list_note_names(vault) == [
            "linked_note",
            "not_included_note",
            "root_note",
        ]

    def test_listing_ignores_anything_that_is_not_a_note(self, tmp_path):
        (tmp_path / "note.md").write_text("# N\n", encoding="utf-8")
        (tmp_path / "photo.png").write_text("x", encoding="utf-8")
        (tmp_path / "sub").mkdir()

        assert list_note_names(tmp_path) == ["note"]

    def test_listing_a_folder_that_does_not_exist_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            list_note_names(tmp_path / "nowhere")
