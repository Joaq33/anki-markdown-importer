"""Tests for the app's dry run: the first thing a user can actually do."""

import asyncio
import threading
import time
from pathlib import Path

import pytest
from textual.widgets import Input, ProgressBar, Static, Switch

from anki_importer.card import Card
from anki_importer.import_run import ImportRun, RunSettings
from tests.test_import_run import FakeAnkiGateway
from anki_importer.notes import FolderNoteSource
from anki_importer.settings_store import load_settings, save_settings
from anki_importer.stage import Stage
from anki_importer.tui.app import AnkiImporterApp
from anki_importer.tui.screens import FolderPickerScreen, HelpScreen, RootNotesScreen
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


class SlowGateway(FakeAnkiGateway):
    """An Anki that can be held mid-import, so cancelling lands mid-flight."""

    def __init__(self):
        super().__init__()
        self.gate = threading.Event()

    def add_note(self, deck_name, card):
        self.gate.wait(10)
        return super().add_note(deck_name, card)

    def release(self):
        self.gate.set()


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


async def wait_for_text(app, text: str, timeout: float = 10.0) -> None:
    """Wait until the notice bar says `text`, however many steps that takes."""
    start = time.monotonic()
    while text not in app.query_one(NoticeBar).notice:
        assert time.monotonic() - start < timeout, app.query_one(NoticeBar).notice
        await asyncio.sleep(0.05)


def make_app(vault, source=None, **overrides) -> AnkiImporterApp:
    """An app pointed at `vault`, without going through the UI."""
    app = AnkiImporterApp(config_path=str(Path(vault) / "test-config.toml"))
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

            table = app.query_one(CardTable)
            row = table.row(table.fronts.index("root_note"))
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

            table = app.query_one(CardTable)
            assert table.row(table.fronts.index("not_included_note")).skipped is True


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


class TestTheConfigScreen:
    async def test_the_config_screen_shows_the_settings_in_use(self, vault):
        app = make_app(vault)
        app.load_settings_from(
            RunSettings(vault_path=str(vault), deck_name="Maths", root_notes=("Indice",))
        )

        async with app.run_test() as pilot:
            await pilot.press("c")
            await pilot.pause()

            screen = app.screen
            assert screen.query_one("#config-deck", Input).value == "Maths"
            assert screen.query_one("#config-roots", Input).value == "Indice"

    async def test_saving_from_the_config_screen_updates_the_app_and_the_file(
        self, vault, config_file
    ):
        app = make_app(vault)
        app.config_path = config_file

        async with app.run_test() as pilot:
            await pilot.press("c")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#config-deck", Input).value = "Maths"
            screen.query_one("#config-upsert", Switch).value = True
            await pilot.click("#config-save")
            await pilot.pause()

            assert app.settings.deck_name == "Maths"
            assert app.settings.upsert is True
            assert load_settings(config_file).deck_name == "Maths"

    async def test_closing_the_config_screen_without_saving_changes_nothing(
        self, vault, config_file
    ):
        app = make_app(vault)
        app.config_path = config_file

        async with app.run_test() as pilot:
            await pilot.press("c")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#config-deck", Input).value = "Changed"
            await pilot.press("escape")
            await pilot.pause()

            assert app.settings.deck_name == "Default"
            assert not config_file.exists()

    async def test_the_app_starts_with_whatever_was_saved_last(
        self, vault, config_file
    ):
        save_settings(
            RunSettings(
                vault_path=str(vault), deck_name="Maths", root_notes=("root_note",)
            ),
            config_file,
        )
        app = AnkiImporterApp(config_path=config_file)

        async with app.run_test():
            assert app.settings.deck_name == "Maths"
            assert app.query_one("#vault-path", Input).value == str(vault)
            assert app.query_one("#root-notes", Input).value == "root_note"

    async def test_every_run_setting_has_a_field_on_the_config_screen(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("c")
            await pilot.pause()
            screen = app.screen

            for field in (
                "#config-vault",
                "#config-deck",
                "#config-roots",
                "#config-prefix",
                "#config-upsert",
                "#config-links",
            ):
                assert screen.query_one(field)


@pytest.fixture
def config_file(tmp_path):
    return tmp_path / "anki-importer.toml"


@pytest.fixture
def gateway():
    return FakeAnkiGateway()


class TestImportingFromTheApp:
    async def _dry_run(self, app, pilot):
        await pilot.press("r")
        await app.workers.wait_for_complete()

    async def test_the_app_offers_a_way_to_import_what_was_found(self, vault):
        app = make_app(vault)

        async with app.run_test():
            assert app.query_one("#submit")

    async def test_importing_sends_every_card_to_the_chosen_deck(self, vault, gateway):
        app = make_app(vault, deck_name="Maths")
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("s")
            await app.workers.wait_for_complete()

            imported = {card.front for card in gateway.notes.values()}
            assert imported == {"root_note", "linked_note"}

    async def test_importing_reports_what_anki_did(self, vault, gateway):
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("s")
            await app.workers.wait_for_complete()

            assert app.query_one(CountBar).counts["added"] == 2

    async def test_importing_first_makes_sure_anki_is_there(self, vault, gateway):
        gateway.online = False
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("s")
            await app.workers.wait_for_complete()

            assert "Anki" in app.query_one(NoticeBar).notice
            assert gateway.notes == {}

    async def test_importing_without_a_dry_run_first_says_so(self, vault, gateway):
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await pilot.press("s")
            await app.workers.wait_for_complete()

            assert "dry run" in app.query_one(NoticeBar).notice
            assert gateway.notes == {}

    async def test_with_updating_on_an_existing_note_is_updated(self, vault, gateway):
        gateway.existing_fronts["Default:root_note"] = 42
        gateway.notes[42] = Card(front="root_note", back="stale")
        app = make_app(vault, upsert=True)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("s")
            await app.workers.wait_for_complete()

            assert gateway.notes[42].back != "stale"
            assert app.query_one(CountBar).counts["updated"] == 1

    async def test_with_updating_off_an_existing_note_is_skipped(self, vault, gateway):
        gateway.existing_fronts["Default:root_note"] = 42
        app = make_app(vault, upsert=False)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("s")
            await app.workers.wait_for_complete()

            assert app.query_one(CountBar).counts["skipped"] == 1

    async def test_a_note_anki_rejects_does_not_stop_the_rest(self, vault, gateway):
        gateway.reject = {"root_note"}
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("s")
            await app.workers.wait_for_complete()

            counts = app.query_one(CountBar).counts
            assert (counts["added"], counts["failed"]) == (1, 1)

    async def test_cancelling_an_import_counts_only_what_was_sent(self, vault):
        held = SlowGateway()
        app = make_app(vault)
        app.gateway = held

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("s")
            await pilot.pause()
            await pilot.press("escape")
            held.release()
            await app.workers.wait_for_complete()

            assert app.query_one(CountBar).counts["added"] <= 1
            assert app.stage is Stage.CANCELLED


class TestInspectingACard:
    async def _dry_run(self, app, pilot):
        await pilot.press("r")
        await app.workers.wait_for_complete()

    async def test_opening_a_card_shows_its_front_tags_and_back(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("enter")
            await pilot.pause()

            screen = app.screen
            assert screen.query_one("#detail-front", Input).value == "root_note"
            assert "root" in screen.query_one("#detail-tags", Input).value
            assert "Root" in str(screen.query_one("#detail-back", Static).content)

    async def test_an_edited_front_is_what_gets_imported(self, vault, gateway):
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("enter")
            await pilot.pause()
            app.screen.query_one("#detail-front", Input).value = "renamed"
            await pilot.click("#detail-apply")
            await pilot.pause()
            app.start_submit()
            await app.workers.wait_for_complete()

            assert "renamed" in {card.front for card in gateway.notes.values()}

    async def test_an_edit_stays_when_the_card_is_opened_again(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("enter")
            await pilot.pause()
            app.screen.query_one("#detail-front", Input).value = "renamed"
            await pilot.click("#detail-apply")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert app.screen.query_one("#detail-front", Input).value == "renamed"

    async def test_a_card_marked_to_skip_is_not_imported(self, vault, gateway):
        (vault / "root_note.md").write_text(
            "---\ntags: [root]\n---\n# Root\n[[not_included_note]]\n", encoding="utf-8"
        )
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            app.screen.query_one("#detail-skip", Switch).value = True
            await pilot.click("#detail-apply")
            await pilot.pause()
            app.start_submit()
            await app.workers.wait_for_complete()

            counts = app.query_one(CountBar).counts
            assert (counts["added"], counts["skipped"]) == (1, 1)

    async def test_editing_one_card_leaves_the_others_alone(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("enter")
            await pilot.pause()
            app.screen.query_one("#detail-front", Input).value = "renamed"
            await pilot.click("#detail-apply")
            await pilot.pause()

            assert sorted(app.query_one(CardTable).fronts) == [
                "linked_note",
                "renamed",
            ]

    async def test_closing_the_detail_without_applying_changes_nothing(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("enter")
            await pilot.pause()
            app.screen.query_one("#detail-front", Input).value = "renamed"
            await pilot.press("escape")
            await pilot.pause()

            assert sorted(app.query_one(CardTable).fronts) == [
                "linked_note",
                "root_note",
            ]


class TestResolvingLinks:
    async def _dry_run(self, app, pilot):
        await pilot.press("r")
        await app.workers.wait_for_complete()

    async def _submit(self, app, pilot):
        await pilot.press("s")
        await app.workers.wait_for_complete()

    async def test_importing_continues_into_resolving_links_on_its_own(
        self, vault, gateway
    ):
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await self._submit(app, pilot)
            await wait_for_text(app, "links resolved")

            assert app.stage is Stage.RESOLVED

    async def test_the_final_count_says_how_many_links_resolved(
        self, vault, gateway
    ):
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await self._submit(app, pilot)
            await wait_for_text(app, "2 links resolved")

    async def test_a_link_that_cannot_be_resolved_names_the_note_to_fix(
        self, vault, gateway
    ):
        (vault / "root_note.md").write_text("See [[nowhere]].\n", encoding="utf-8")
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await self._submit(app, pilot)
            await wait_for_text(app, "could not be resolved")

            assert "nowhere" in app.query_one(NoticeBar).notice

    async def test_when_nothing_links_anywhere_it_says_so(self, vault, gateway):
        (vault / "root_note.md").write_text("Just text.\n", encoding="utf-8")
        (vault / "linked_note.md").write_text("Just text.\n", encoding="utf-8")
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await self._submit(app, pilot)
            await wait_for_text(app, "No links")

            assert app.stage is Stage.RESOLVED

    async def test_with_link_generation_off_the_step_is_visibly_skipped(
        self, vault, gateway
    ):
        app = make_app(vault, generate_links=False)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await self._submit(app, pilot)
            await wait_for_text(app, "Imported")

            assert app.stage is Stage.IMPORTED
            assert any(
                "skipping link resolution" in line
                for line in app.query_one(LogPanel).entries
            )

    async def test_cancelling_an_import_does_not_resolve_links(self, vault):
        held = SlowGateway()
        app = make_app(vault)
        app.gateway = held

        async with app.run_test() as pilot:
            await self._dry_run(app, pilot)
            await pilot.press("s")
            await pilot.pause()
            await pilot.press("escape")
            held.release()
            await app.workers.wait_for_complete()

            assert app.stage is Stage.CANCELLED


class TestHelp:
    async def test_pressing_question_mark_explains_what_you_can_do(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.click(CardTable)
            await pilot.press("?")
            await pilot.pause()

            assert isinstance(app.screen, HelpScreen)
            explained = app.screen.explained_keys()
            for key in ("r", "s", "e", "c", "l", "escape", "q"):
                assert key in explained

    async def test_the_help_button_explains_things_too(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.click("#help")
            await pilot.pause()

            assert isinstance(app.screen, HelpScreen)

    async def test_every_keybinding_the_app_offers_is_explained_in_the_help(
        self, vault
    ):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.click(CardTable)
            await pilot.press("?")
            await pilot.pause()

            explained = app.screen.explained_keys()
            for binding in app.BINDINGS:
                assert binding.key in explained, binding.key

    async def test_the_help_closes_and_you_are_where_you_were(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.click(CardTable)
            await pilot.press("?")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            assert not isinstance(app.screen, HelpScreen)

    async def test_help_opens_from_the_settings_screen_too(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("c")
            await pilot.pause()
            await pilot.click("#config-help")
            await pilot.pause()

            assert isinstance(app.screen, HelpScreen)


class TestSnapshots:
    """What the screens look like, pixel for pixel.

    These run against the repo's own fixture vault through a relative path,
    so the snapshots hold on any machine and whatever else ran before them.
    """

    def _snapshot_app(self, tmp_path, **overrides):
        app = AnkiImporterApp(config_path=str(tmp_path / "snap.toml"))
        settings = {
            "vault_path": "tests/test_notes",
            "root_notes": ("root_note",),
            "throttle_seconds": 0.0,
        }
        app.load_settings_from(RunSettings(**{**settings, **overrides}))
        return app

    def test_the_main_screen(self, snap_compare, tmp_path):
        assert snap_compare(self._snapshot_app(tmp_path), terminal_size=(100, 30))

    def test_the_settings_screen(self, snap_compare, tmp_path):
        async def open_settings(pilot):
            await pilot.press("c")
            await pilot.pause()

        assert snap_compare(
            self._snapshot_app(tmp_path),
            terminal_size=(100, 30),
            run_before=open_settings,
        )

    def test_a_card_up_close(self, snap_compare, tmp_path):
        app = self._snapshot_app(tmp_path)

        async def open_first_card(pilot):
            await pilot.press("r")
            for _ in range(200):
                if app.query_one(CardTable).fronts:
                    break
                await asyncio.sleep(0.05)
            await pilot.press("enter")
            await pilot.pause()

        assert snap_compare(app, terminal_size=(100, 34), run_before=open_first_card)

    def test_a_finished_dry_run(self, snap_compare, tmp_path):
        app = self._snapshot_app(tmp_path)

        async def finish_a_dry_run(pilot):
            await pilot.press("r")
            for _ in range(200):
                if len(app.query_one(CardTable).fronts) == 3:
                    break
                await asyncio.sleep(0.05)
            await pilot.pause()

        assert snap_compare(app, terminal_size=(100, 30), run_before=finish_a_dry_run)


class TestReviewFixes:
    async def test_changing_the_folder_on_the_main_screen_is_remembered(
        self, vault, config_file
    ):
        app = make_app(vault)
        app.config_path = config_file

        async with app.run_test() as pilot:
            app.query_one("#vault-path", Input).value = str(vault)
            app.query_one("#root-notes", Input).value = "root_note, linked_note"
            await pilot.press("r")
            await app.workers.wait_for_complete()

            assert load_settings(config_file).root_notes == (
                "root_note",
                "linked_note",
            )

    async def test_help_opens_from_a_card_up_close(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("r")
            await app.workers.wait_for_complete()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.click("#detail-help")
            await pilot.pause()

            assert isinstance(app.screen, HelpScreen)

    async def test_opening_a_card_from_an_empty_table_does_nothing(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.press("e")
            await pilot.pause()

            assert not isinstance(app.screen, HelpScreen)
            from anki_importer.tui.screens import CardDetailScreen

            assert not isinstance(app.screen, CardDetailScreen)


class TestPickers:
    async def test_browse_opens_a_folder_picker(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.click("#browse")
            await pilot.pause()

            assert isinstance(app.screen, FolderPickerScreen)

    async def test_choosing_a_folder_fills_the_vault_field(self, tmp_path):
        real = tmp_path / "vault"
        real.mkdir()
        (real / "note.md").write_text("# N\n", encoding="utf-8")
        app = make_app(tmp_path)

        async with app.run_test() as pilot:
            await pilot.click("#browse")
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.click("#picker-use")
            await pilot.pause()

            assert app.query_one("#vault-path", Input).value == str(real)

    async def test_roots_opens_a_checklist_of_the_vaults_notes(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.click("#pick-roots")
            await pilot.pause()

            screen = app.screen
            assert isinstance(screen, RootNotesScreen)
            assert screen.shown_notes() == [
                "linked_note",
                "not_included_note",
                "root_note",
            ]
            assert screen.chosen_notes() == ["root_note"]

    async def test_applying_the_checklist_fills_the_roots_field(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            await pilot.click("#pick-roots")
            await pilot.pause()
            await pilot.press("space")
            await pilot.click("#roots-apply")
            await pilot.pause()

            assert app.query_one("#root-notes", Input).value == (
                "root_note, linked_note"
            )

    async def test_a_checklist_for_a_missing_vault_explains_itself(self, tmp_path):
        app = make_app(tmp_path)
        app.load_settings_from(
            RunSettings(vault_path=str(tmp_path / "nowhere"), root_notes=("x",))
        )

        async with app.run_test() as pilot:
            await pilot.click("#pick-roots")
            await pilot.pause()

            assert "does not exist" in app.query_one(NoticeBar).notice

    async def test_typing_a_note_name_suggests_the_rest(self, vault):
        app = make_app(vault)

        async with app.run_test() as pilot:
            field = app.query_one("#root-notes", Input)
            await pilot.click("#root-notes")
            field.value = "root_note, link"
            await pilot.pause()
            await pilot.press("end")
            await pilot.press("right")
            await pilot.pause()

            assert field.value == "root_note, linked_note"

    async def test_the_deck_field_suggests_what_anki_knows(self, vault, gateway):
        gateway.deck_names_list = ["Default", "Maths"]
        app = make_app(vault)
        app.gateway = gateway

        async with app.run_test() as pilot:
            await app.workers.wait_for_complete()
            await pilot.press("c")
            await pilot.pause()
            field = app.screen.query_one("#config-deck", Input)
            await pilot.click("#config-deck")
            field.value = "Ma"
            await pilot.pause()
            await pilot.press("end")
            await pilot.press("right")
            await pilot.pause()

            assert field.value == "Maths"
