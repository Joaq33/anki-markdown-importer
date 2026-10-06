"""Tests for the app's dry run: the first thing a user can actually do."""

import pytest

from anki_importer.import_run import ImportRun, RunSettings
from anki_importer.notes import FolderNoteSource
from anki_importer.stage import Stage
from anki_importer.tui.app import AnkiImporterApp
from anki_importer.tui.widgets import CardTable, NoticeBar

LINKED_PAIR = {
    "root_note.md": "---\ntags: [root]\n---\n# Root\nSee [[linked_note]].\n",
    "linked_note.md": "---\ntags: [linked]\n---\n# Linked\nBack to [[root_note]].\n",
    "not_included_note.md": "---\ntags: [not_included]\n---\n# Skipped\n",
}


@pytest.fixture
def vault(tmp_path):
    for name, content in LINKED_PAIR.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    return tmp_path


def make_app(vault, **overrides) -> AnkiImporterApp:
    """An app pointed at `vault`, without going through the UI."""
    app = AnkiImporterApp()
    app.load_settings_from(
        RunSettings(
            vault_path=str(vault),
            root_notes=("root_note",),
            throttle_seconds=0.0,
            **overrides,
        )
    )
    return app


class TestTheAppStarts:
    async def test_the_app_offers_a_folder_a_set_of_root_notes_and_a_run_button(
        self, vault
    ):
        app = make_app(vault)

        async with app.run_test():
            assert app.query_one("#vault-path")
            assert app.query_one("#root-notes")
            assert app.query_one("#run")

    async def test_the_app_shows_the_folder_and_root_notes_it_will_use(self, vault):
        app = make_app(vault)

        async with app.run_test():
            assert app.query_one("#vault-path").value == str(vault)
            assert app.query_one("#root-notes").value == "root_note"

    async def test_the_app_starts_by_saying_nothing_has_been_imported_yet(self, vault):
        app = make_app(vault)

        async with app.run_test():
            assert app.query_one(NoticeBar).notice == Stage.IDLE.message
            assert app.query_one(CardTable).fronts == []


class TestADryRun:
    async def test_a_dry_run_lists_a_card_for_every_note_the_graph_reaches(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert sorted(app.query_one(CardTable).fronts) == [
                "linked_note",
                "root_note",
            ]

    async def test_a_dry_run_reports_which_notes_were_found(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert app.query_one(NoticeBar).notice == "Found 2 notes"

    async def test_a_dry_run_leaves_you_able_to_run_again(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert sorted(app.query_one(CardTable).fronts) == [
                "linked_note",
                "root_note",
            ]

    async def test_a_dry_run_never_contacts_anki(self, vault):
        app = make_app(vault)
        app.gateway = None

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert app.query_one(CardTable).fronts


class TestWhatAListedCardShows:
    async def test_a_listed_card_shows_its_front_and_its_tags(self, vault):
        (vault / "root_note.md").write_text(
            "---\ntags: [root, calculus]\n---\n# Root\n", encoding="utf-8"
        )
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            row = app.query_one(CardTable).row("root_note")
            assert row.front == "root_note"
            assert "calculus" in row.tags

    async def test_a_card_that_will_not_be_imported_is_marked_as_skipped(self, vault):
        (vault / "root_note.md").write_text(
            "---\ntags: [root]\n---\n# Root\n[[not_included_note]]\n", encoding="utf-8"
        )
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert app.query_one(CardTable).row("not_included_note").skipped is True


class TestProblemsAreReportedNotRaised:
    async def test_a_folder_that_does_not_exist_is_reported_instead_of_crashing(
        self, tmp_path
    ):
        app = make_app(tmp_path)
        app.load_settings_from(
            RunSettings(vault_path=str(tmp_path / "nowhere"), root_notes=("root_note",))
        )

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert "does not exist" in app.query_one(NoticeBar).notice
            assert app.query_one(CardTable).fronts == []

    async def test_starting_with_no_root_notes_says_so_instead_of_doing_nothing(
        self, vault
    ):
        app = make_app(vault)
        app.load_settings_from(RunSettings(vault_path=str(vault)))

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert app.query_one(NoticeBar).notice != Stage.IDLE.message
            assert app.query_one(CardTable).fronts == []

    async def test_a_link_to_a_note_that_is_not_in_the_vault_is_reported(self, vault):
        (vault / "root_note.md").write_text("[[nowhere]]\n", encoding="utf-8")
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert "nowhere" in app.query_one(NoticeBar).notice
            assert any(
                "nowhere" in problem for problem in app.query_one(NoticeBar).problems
            )