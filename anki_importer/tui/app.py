"""The terminal UI.

The app owns the screen; the import itself runs on a worker thread and reports
back as events, so a long import never freezes the interface and can be stopped.
"""

import queue
from collections.abc import Callable
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, ProgressBar

from ..card import Card
from ..gateway import AnkiConnectGateway, AnkiGateway
from ..import_run import (
    BuildEvent,
    CardBuilt,
    CardSubmitted,
    ImportRun,
    NoteDiscovered,
    NoteUnreadable,
    RunFinished,
    RunSettings,
    RunStarted,
    RunSummary,
    SubmitEvent,
    parse_root_notes,
)
from ..notes import FolderNoteSource, NoteSource
from ..stage import Stage
from ..logging_setup import remove_sink, take_over_terminal
from ..settings_store import DEFAULT_FILE_NAME, load_settings, save_settings
from .screens import ConfigScreen
from .widgets import CardTable, CountBar, LogPanel, NoticeBar


class AnkiImporterApp(App[None]):
    """Import Obsidian notes into Anki, watching it happen."""

    TITLE = "Anki importer"
    CSS = """
    #controls { height: auto; padding: 0 1; }
    #controls Label { width: 14; padding: 1 1 0 0; }
    #vault-path, #root-notes { width: 1fr; }
    #buttons { height: auto; padding: 1 0 0 0; }
    #notice { height: auto; padding: 1 1 0 1; }
    #counts { height: auto; padding: 0 1; }
    #progress { height: 1; }
    #cards { height: 1fr; }
    #log { height: 10; border-top: solid $accent; }
    """
    BINDINGS = [
        Binding("r", "run", "Run"),
        Binding("s", "submit", "Import"),
        Binding("escape", "cancel", "Cancel"),
        Binding("l", "log_panel", "Logs"),
        Binding("c", "config", "Settings"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config_path: str | Path | None = None) -> None:
        super().__init__()
        self.config_path = Path(config_path) if config_path else Path.cwd() / DEFAULT_FILE_NAME
        self.settings = load_settings(self.config_path)
        self.source: NoteSource | None = None
        # Where notes come from. Overridable so tests can hold a run open.
        self.source_factory: Callable[[str], NoteSource] = FolderNoteSource
        self.gateway: AnkiGateway | None = None
        self.import_run: ImportRun | None = None
        self.stage = Stage.IDLE
        self.problems: list[str] = []
        self._mounted = False
        self._log_sink: int | None = None
        # Log lines can arrive from a worker thread, so they queue up and the
        # app drains them on its own thread.
        self._pending_lines: queue.Queue[str] = queue.Queue()

    # -- composition ---------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="controls"):
            with Horizontal(classes="field"):
                yield Label("Vault folder")
                yield Input(placeholder="vaults/mi-vault", id="vault-path")
            with Horizontal(classes="field"):
                yield Label("Root notes")
                yield Input(placeholder="Root notes, comma separated", id="root-notes")
            with Horizontal(id="buttons"):
                yield Button("Run dry run", id="run", variant="primary")
                yield Button("Import into Anki", id="submit", variant="success")
        yield NoticeBar(Stage.IDLE.message, id="notice")
        yield CountBar(id="counts")
        yield ProgressBar(id="progress")
        yield CardTable(id="cards")
        yield LogPanel(id="log")

    def on_mount(self) -> None:
        self._mounted = True
        self._log_sink = take_over_terminal(self._queue_log_line)
        self.set_interval(0.05, self._drain_log_queue)
        self.sync_inputs()

    def _queue_log_line(self, line: str) -> None:
        """Called by loguru, on whichever thread logged."""
        self._pending_lines.put(str(line))

    def _log_panel(self) -> LogPanel | None:
        """The log panel, unless it is hidden or not built yet."""
        if not self._mounted:
            return None
        panels = self.query(LogPanel)
        return panels.first() if len(panels) else None

    def _drain_log_queue(self) -> None:
        """Move queued log lines into the panel, on the app's own thread."""
        panel = self._log_panel()
        if panel is None:
            return
        while True:
            try:
                panel.add_line(self._pending_lines.get_nowait())
            except queue.Empty:
                return

    def write_log(self, line: str) -> None:
        """Show a log line straight away, from the app's own thread."""
        panel = self._log_panel()
        if panel is not None:
            panel.add_line(line)

    def on_unmount(self) -> None:
        if self._log_sink is not None:
            remove_sink(self._log_sink)
            self._log_sink = None

    def _on_log_line(self, line: str) -> None:
        """A log line from anywhere in the app, shown in our own panel."""


    def sync_inputs(self) -> None:
        """Show the settings we will use in the fields you can change."""
        if not self._mounted:
            return
        self.query_one("#vault-path", Input).value = self.settings.vault_path
        self.query_one("#root-notes", Input).value = ", ".join(self.settings.root_notes)

    def load_settings_from(self, settings: RunSettings) -> None:
        """Adopt a set of settings, without touching Anki or the disk."""
        self.settings = settings
        self.sync_inputs()

    def read_settings_from_inputs(self) -> RunSettings:
        """The settings as typed in the fields, keeping the rest as configured."""
        if not self._mounted:
            return self.settings
        return RunSettings(
            vault_path=self.query_one("#vault-path", Input).value.strip(),
            deck_name=self.settings.deck_name,
            root_notes=parse_root_notes(self.query_one("#root-notes", Input).value),
            card_prefix=self.settings.card_prefix,
            upsert=self.settings.upsert,
            generate_links=self.settings.generate_links,
            throttle_seconds=self.settings.throttle_seconds,
        )

    # -- what the user sees ---------------------------------------------------

    @property
    def cards(self) -> list[Card]:
        return self.import_run.cards if self.import_run else []

    def announce(self, stage: Stage, problems: list[str] | None = None) -> None:
        self.stage = stage
        self.problems = list(problems or [])
        self.query_one(NoticeBar).report(stage.message, self.problems)

    @on(Button.Pressed, "#run")
    def _on_run_pressed(self) -> None:
        self.start_dry_run()

    @on(Button.Pressed, "#submit")
    def _on_submit_pressed(self) -> None:
        self.start_submit()

    def action_config(self) -> None:
        """Open the settings screen, and keep what is saved there."""
        self.push_screen(ConfigScreen(self.settings), self._on_settings_saved)

    def _on_settings_saved(self, settings: RunSettings | None) -> None:
        if settings is None:
            return
        self.settings = settings
        save_settings(settings, self.config_path)
        self.sync_inputs()

    def report_found(self, found: int, problems: list[str]) -> None:
        """Say how many notes a dry run found, and what went wrong."""
        if found:
            self.stage = Stage.DISCOVERED
            self.problems = problems
            noun = "note" if found == 1 else "notes"
            self.query_one(NoticeBar).report(f"Found {found} {noun}", problems)
        else:
            self.announce(Stage.DISCOVERED, problems or ["Nothing to import"])

    # -- running a dry run ---------------------------------------------------

    def action_run(self) -> None:
        self.start_dry_run()

    def start_dry_run(self) -> None:
        """Discover and build every card, without sending anything to Anki."""
        settings = self.read_settings_from_inputs()
        self.settings = settings
        try:
            source: NoteSource = self.source_factory(settings.vault_path)
        except FileNotFoundError as error:
            self.announce(Stage.IDLE, [str(error)])
            return
        if not settings.root_notes:
            self.announce(Stage.IDLE, ["Choose at least one root note to start from"])
            return

        self.source = source
        self.query_one(CardTable).clear_cards()
        self.query_one(CountBar).reset()
        panel = self._log_panel()
        if panel is not None:
            panel.clear_entries()
        progress = self.query_one(ProgressBar)
        progress.total = None
        progress.progress = 0
        self.announce(Stage.DISCOVERING)
        self.import_run = ImportRun(settings, source=source)
        self._discover_and_build(self.import_run)

    @work(thread=True, exclusive=True, group="import")
    def _discover_and_build(self, import_run: ImportRun) -> None:
        try:
            for event in import_run.build_cards():
                self.call_from_thread(self._on_build_event, event)
        except Exception as error:
            self.call_from_thread(self.announce, Stage.IDLE, [str(error)])

    def _on_build_event(self, event: BuildEvent) -> None:
        match event:
            case RunStarted(stage):
                self.announce(stage)
            case RunFinished():
                self._finish_discovery()
            case NoteDiscovered(name):
                self.write_log(f"Found note '{name}'")
            case NoteUnreadable(name):
                self.write_log(f"WARNING no note called '{name}': a link points at nothing")
                self.problems.append(f"no note called '{name}'")
                self._tally()
            case CardBuilt(card):
                self.query_one(CardTable).add_card(card)
                self._tally()

    def _tally(self) -> None:
        """Keep the counts and the progress bar in step with what we have."""
        counts = self.query_one(CountBar)
        counts.tally(
            found=len(self.cards),
            missing=len(self.import_run.missing) if self.import_run else 0,
        )

    def _finish_discovery(self) -> None:
        """A run has stopped: mark the bar complete and say what was found."""
        found = len(self.cards)
        progress = self.query_one(ProgressBar)
        progress.total = found or 1
        progress.progress = found
        self.report_found(found, self.problems)

    # -- importing into Anki -------------------------------------------------

    def action_submit(self) -> None:
        self.start_submit()

    def start_submit(self) -> None:
        """Send the cards from the last dry run to Anki."""
        settings = self.read_settings_from_inputs()
        self.settings = settings
        gateway = self.gateway or AnkiConnectGateway()
        self.gateway = gateway
        run = self.import_run
        if run is None or not run.cards:
            self.announce(Stage.IDLE, ["Nothing to import yet - run a dry run first"])
            return

        self.announce(Stage.IMPORTING)
        progress = self.query_one(ProgressBar)
        progress.total = len(run.cards)
        progress.progress = 0
        self._submit(run, gateway)

    @work(thread=True, exclusive=True, group="import")
    def _submit(self, run: ImportRun, gateway: AnkiGateway) -> None:
        if not gateway.is_available():
            self.call_from_thread(
                self.announce,
                Stage.IDLE,
                [
                    "Could not reach Anki. "
                    "Start it with the AnkiConnect add-on installed, then try again."
                ],
            )
            return
        try:
            for event in run.submit(gateway):
                self.call_from_thread(self._on_submit_event, event)
        except Exception as error:
            self.call_from_thread(self.announce, Stage.IDLE, [str(error)])

    def _on_submit_event(self, event: SubmitEvent) -> None:
        match event:
            case CardSubmitted(front, outcome):
                self.write_log(f"{outcome.value}: {front}")
                if self.import_run is not None:
                    self.query_one(CountBar).imported(self.import_run.summary)
                    self.query_one(ProgressBar).progress = self.import_run.summary.processed
            case RunSummary() as summary:
                self.query_one(CountBar).imported(summary)
                self._finish_submit(summary)

    def _finish_submit(self, summary: RunSummary) -> None:
        """Say what Anki did, unless cancelling already had the last word."""
        run = self.import_run
        if run is not None and run.cancelled:
            self.announce(Stage.CANCELLED)
            return
        parts = ", ".join(
            f"{value} {name}"
            for name, value in (
                ("added", summary.added),
                ("updated", summary.updated),
                ("skipped", summary.skipped),
                ("failed", summary.failed),
            )
            if value
        )
        noun = "note" if summary.processed == 1 else "notes"
        problems = [f"{summary.failed} failed to import"] if summary.failed else []
        self.stage = Stage.IMPORTED
        self.problems = problems
        self.query_one(NoticeBar).report(f"Imported {summary.processed} {noun}: {parts}", problems)

    def action_cancel(self) -> None:
        """Stop the run in flight, keeping whatever it has found."""
        if self.import_run is None:
            return
        self.import_run.cancel()
        self.write_log("Cancelled. The notes found so far are still here.")
        self.announce(Stage.CANCELLED)
        self.query_one(ProgressBar).total = None
        self.query_one(ProgressBar).progress = 0

    def action_log_panel(self) -> None:
        """Show or hide the run's log."""
        panel = self._log_panel()
        if panel is None:
            return
        if panel.display:
            panel.hide_panel()
        else:
            panel.show_panel()