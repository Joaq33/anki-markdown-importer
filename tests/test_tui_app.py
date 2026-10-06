"""Tests for the app's dry run: the first thing a user can actually do."""

import threading

import pytest
from textual.widgets import ProgressBar

from anki_importer.import_run import ImportRun, RunSettings
from anki_importer.notes import FolderNoteSource
from anki_importer.stage import Stage
from anki_importer.tui.app import AnkiImporterApp
from anki_importer.tui.widgets import CardTable, CountBar, LogPanel, NoticeBar

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


@pytest.fixture
def big_vault(tmp_path):
    """A vault with enough notes that a run is still going when we look."""
    for index in range(400):
        (tmp_path / f"note_{index:03d}.md").write_text(f"note {index}\n", "utf-8")
    (tmp_path / "root_note.md").write_text(
        "\n".join(f"[[note_{index:03d}]]" for index in range(400)), "utf-8"
    )
    return tmp_path


class GatedNoteSource:
    """A vault that can be held shut, so a run can be caught while it works."""

    def __init__(self, vault):
        self._inner = FolderNoteSource(vault)
        self.opened = threading.Event()

    def read(self, name):
        self.opened.wait(10)
        return self._inner.read(name)

    def open(self):
        self.opened.set()


def make_app(vault, source=None, **overrides) -> AnkiImporterApp:
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
    if source is not None:
        app.source_factory = lambda _path: source
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

class TestProgress:
    async def test_a_dry_run_shows_how_far_along_it_is(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert app.query_one(ProgressBar).total == 2
            assert app.query_one(ProgressBar).progress == 2

    async def test_progress_starts_at_nothing_done(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert app.query_one(ProgressBar).total is not None

    async def test_the_app_says_it_is_working_while_a_run_is_in_flight(self, vault):
        source = GatedNoteSource(vault)
        app = make_app(vault, source=source)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()

            assert app.query_one(NoticeBar).notice == Stage.DISCOVERING.message

            source.open()
            await app.workers.wait_for_complete()
            assert app.query_one(CardTable).fronts

    async def test_the_counts_say_how_many_notes_were_found_and_how_many_are_missing(
        self, vault
    ):
        (vault / "root_note.md").write_text("[[nowhere]]\n[[linked_note]]\n", "utf-8")
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            counts = app.query_one(CountBar).counts
            assert counts["found"] == 2
            assert counts["missing"] == 1


class TestTheLogPanel:
    async def test_the_panels_hold_the_runs_log_output(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            panel = app.query_one(LogPanel)
            assert any("root_note" in line for line in panel.entries)

    async def test_a_problem_is_shown_in_the_log_as_well_as_the_notice(self, vault):
        (vault / "root_note.md").write_text("[[nowhere]]\n", encoding="utf-8")
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert any("nowhere" in line for line in app.query_one(LogPanel).entries)

    async def test_nothing_is_printed_outside_the_app_while_it_runs(
        self, vault, capsys
    ):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()

        printed = capsys.readouterr()
        assert printed.out == ""
        assert printed.err == ""

    async def test_the_panel_can_be_hidden_and_shown_again(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            panel = app.query_one(LogPanel)
            await pilot.press("l")
            assert panel.display is False
            await pilot.press("l")
            assert panel.display is True


class TestCancelling:
    async def test_cancelling_stops_the_run(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()
            await pilot.press("escape")

            assert app.stage is Stage.CANCELLED

    async def test_cancelling_keeps_the_notes_already_found(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()
            await pilot.press("escape")

            assert app.query_one(CardTable).fronts

    async def test_the_app_is_ready_to_run_again_after_a_cancelled_run(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()
            await pilot.press("escape")
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert app.query_one(CardTable).fronts

    async def test_cancelling_a_run_that_is_still_going_stops_it_quickly(self, vault):
        source = GatedNoteSource(vault)
        app = make_app(vault, source=source)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            await pilot.press("escape")
            source.open()
            await app.workers.wait_for_complete()

            assert app.stage is Stage.CANCELLED
            assert app.query_one(CardTable).fronts == []
