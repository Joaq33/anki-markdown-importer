"""The terminal UI.

The app owns the screen; the import itself runs on a worker thread and reports
back as events, so a long import never freezes the interface and can be stopped.
"""

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label

from ..card import Card
from ..gateway import AnkiGateway
from ..import_run import (
    BuildEvent,
    CardBuilt,
    ImportRun,
    NoteDiscovered,
    NoteUnreadable,
    RunFinished,
    RunSettings,
    RunStarted,
    parse_root_notes,
)
from ..notes import FolderNoteSource, NoteSource
from ..stage import Stage
from .widgets import CardTable, NoticeBar


class AnkiImporterApp(App[None]):
    """Import Obsidian notes into Anki, watching it happen."""

    TITLE = "Anki importer"
    CSS = """
    #controls { height: auto; padding: 0 1; }
    #controls Label { width: 14; padding: 1 1 0 0; }
    #vault-path, #root-notes { width: 1fr; }
    #buttons { height: auto; padding: 1 0 0 0; }
    #notice { height: auto; padding: 1 1; }
    #cards { height: 1fr; }
    """
    BINDINGS = [
        Binding("r", "run", "Run"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.settings = RunSettings(vault_path="")
        self.source: NoteSource | None = None
        self.gateway: AnkiGateway | None = None
        self.import_run: ImportRun | None = None
        self.stage = Stage.IDLE
        self.problems: list[str] = []
        self._mounted = False

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
        yield NoticeBar(Stage.IDLE.message, id="notice")
        yield CardTable(id="cards")
        yield Footer()

    def on_mount(self) -> None:
        self._mounted = True
        self.sync_inputs()

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
            source: NoteSource = FolderNoteSource(settings.vault_path)
        except FileNotFoundError as error:
            self.announce(Stage.IDLE, [str(error)])
            return
        if not settings.root_notes:
            self.announce(Stage.IDLE, ["Choose at least one root note to start from"])
            return

        self.source = source
        self.query_one(CardTable).clear_cards()
        self.announce(Stage.DISCOVERING)
        self._discover_and_build(settings, source)

    @work(thread=True, exclusive=True, group="import")
    def _discover_and_build(self, settings: RunSettings, source: NoteSource) -> None:
        import_run = ImportRun(settings, source=source)
        self.call_from_thread(self._start, import_run)
        try:
            for event in import_run.build_cards():
                self.call_from_thread(self._on_build_event, event)
        except Exception as error:
            self.call_from_thread(self.announce, Stage.IDLE, [str(error)])

    def _start(self, import_run: ImportRun) -> None:
        self.import_run = import_run
        self.announce(Stage.DISCOVERING)

    def _on_build_event(self, event: BuildEvent) -> None:
        match event:
            case RunStarted(stage):
                self.announce(stage)
            case RunFinished():
                self.report_found(len(self.cards), self.problems)
            case NoteDiscovered():
                pass
            case NoteUnreadable(name):
                self.problems.append(f"no note called '{name}'")
            case CardBuilt(card):
                self.query_one(CardTable).add_card(card)