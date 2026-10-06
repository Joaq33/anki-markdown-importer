"""The screens the app can show, beyond the one it starts on."""

from collections.abc import Iterable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.suggester import SuggestFromList
from textual.widgets import (
    Button,
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    SelectionList,
    Static,
    Switch,
)
from textual.widgets._selection_list import Selection

from ..card import Card
from ..import_run import RunSettings, parse_root_notes
from ..preview import plain_preview


class ConfigScreen(Screen[RunSettings | None]):
    """Every run setting, editable and saveable.

    Dismisses with the new settings when saved, or with nothing when cancelled.
    """

    TITLE = "Settings"
    CSS = """
    ConfigScreen { align: center middle; }
    #config-box { width: 72; height: auto; border: solid $accent; padding: 1 2; }
    #config-box Label { width: 18; padding: 1 1 0 0; }
    #config-upsert, #config-links { width: auto; }
    #config-actions { height: auto; padding: 1 0 0 0; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self, settings: RunSettings, deck_names: tuple[str, ...] = ()
    ) -> None:
        super().__init__()
        self.settings = settings
        self._deck_names = deck_names

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-box"):
            with Horizontal():
                yield Label("Vault folder")
                yield Input(self.settings.vault_path, id="config-vault")
            with Horizontal():
                yield Label("Deck name")
                yield Input(
                    self.settings.deck_name,
                    id="config-deck",
                    suggester=SuggestFromList(
                        self._deck_names, case_sensitive=False
                    ),
                )
            with Horizontal():
                yield Label("Root notes")
                yield Input(", ".join(self.settings.root_notes), id="config-roots")
            with Horizontal():
                yield Label("Card prefix")
                yield Input(self.settings.card_prefix, id="config-prefix")
            with Horizontal():
                yield Label("Update existing")
                yield Switch(self.settings.upsert, id="config-upsert")
            with Horizontal():
                yield Label("Make link ids")
                yield Switch(self.settings.generate_links, id="config-links")
            with Horizontal(id="config-actions"):
                yield Button("Save", id="config-save", variant="primary")
                yield Button("Cancel", id="config-cancel")
                yield Button("Help", id="config-help")
        yield Footer()

    def read_settings(self) -> RunSettings:
        """The settings as typed, keeping the runs's non-editable details."""
        return RunSettings(
            vault_path=self.query_one("#config-vault", Input).value.strip(),
            deck_name=self.query_one("#config-deck", Input).value.strip() or "Default",
            root_notes=parse_root_notes(self.query_one("#config-roots", Input).value),
            card_prefix=self.query_one("#config-prefix", Input).value,
            upsert=self.query_one("#config-upsert", Switch).value,
            generate_links=self.query_one("#config-links", Switch).value,
            throttle_seconds=self.settings.throttle_seconds,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "config-save":
            self.dismiss(self.read_settings())
        elif event.button.id == "config-help":
            self.app.push_screen(HelpScreen())
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

class CardDetailScreen(Screen[tuple[int, Card] | None]):
    """One card, up close: what it says, what it is tagged, whether it goes.

    Dismisses with the card's position and its edited self when applied,
    or with nothing when closed without applying.
    """

    TITLE = "Card"
    CSS = """
    CardDetailScreen { align: center middle; }
    #detail-box { width: 76; height: auto; max-height: 90%; border: solid $accent; padding: 1 2; }
    #detail-box Label { width: 12; padding: 1 1 0 0; }
    #detail-back { height: auto; max-height: 16; border: solid $primary; padding: 0 1; }
    #detail-actions { height: auto; padding: 1 0 0 0; }
    """
    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    def __init__(self, index: int, card: Card) -> None:
        super().__init__()
        self.index = index
        self.card = card

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="detail-box"):
            with Horizontal():
                yield Label("Front")
                yield Input(self.card.front, id="detail-front")
            with Horizontal():
                yield Label("Tags")
                yield Input(", ".join(sorted(self.card.tags)), id="detail-tags")
            with Horizontal():
                yield Label("Skip")
                yield Switch(self.card.should_skip, id="detail-skip")
            yield Label("Back preview")
            with VerticalScroll(id="detail-back-scroll"):
                yield Static(plain_preview(self.card.back), id="detail-back")
            with Horizontal(id="detail-actions"):
                yield Button("Apply", id="detail-apply", variant="primary")
                yield Button("Close", id="detail-close")
                yield Button("Help", id="detail-help")
        yield Footer()

    def read_card(self) -> Card:
        """The card as edited, keeping everything the screen cannot change."""
        tags = {
            tag.strip()
            for tag in self.query_one("#detail-tags", Input).value.split(",")
            if tag.strip()
        }
        return Card(
            front=self.query_one("#detail-front", Input).value,
            back=self.card.back,
            frontmatter=self.card.frontmatter,
            staged_content=self.card.staged_content,
            should_skip=self.query_one("#detail-skip", Switch).value,
            tags=tags,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "detail-apply":
            self.dismiss((self.index, self.read_card()))
        elif event.button.id == "detail-help":
            self.app.push_screen(HelpScreen())
        else:
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


HELP_ENTRIES: tuple[tuple[str, str, str], ...] = (
    ("r", "Run a dry run", "walk the vault, list every card it would import"),
    ("s", "Import into Anki", "send the dry run's cards to the chosen deck"),
    ("e", "Inspect a card", "open the highlighted row to check or fix it"),
    ("enter", "Inspect a card", "same as e, straight from the table"),
    ("c", "Settings", "vault, deck, roots, prefix, updating, links"),
    ("l", "Show or hide the log", "the run's own log panel"),
    ("escape", "Cancel or close", "stop the run in flight, or close a panel"),
    ("?", "This help", "whenever you are not typing in a field"),
    ("q", "Quit", "leave the app"),
)


class HelpScreen(Screen[None]):
    """What you can press, and what it does."""

    TITLE = "Help"
    CSS = """
    HelpScreen { align: center middle; }
    #help-box { width: 78; height: auto; max-height: 90%; border: solid $accent; padding: 1 2; }
    #help-keys { height: auto; max-height: 18; }
    #help-actions { height: auto; padding: 1 0 0 0; }
    """
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("?", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="help-box"):
            yield DataTable(id="help-keys")
            with Horizontal(id="help-actions"):
                yield Button("Close", id="help-close", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#help-keys", DataTable)
        table.add_column("Key", key="key")
        table.add_column("Does", key="does")
        table.add_column("When", key="when")
        table.cursor_type = "row"
        for key, does, when in HELP_ENTRIES:
            table.add_row(key, does, when)

    def explained_keys(self) -> tuple[str, ...]:
        """Every key this panel claims to explain."""
        return tuple(key for key, _, _ in HELP_ENTRIES)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class DirectoryPicker(DirectoryTree):
    """A directory tree that only shows directories: you pick a vault, not a file."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if path.is_dir()]


class FolderPickerScreen(Screen[str | None]):
    """Choose the vault folder by pointing at it.

    Dismisses with the chosen folder, or with nothing when cancelled.
    """

    TITLE = "Choose vault folder"
    CSS = """
    FolderPickerScreen { align: center middle; }
    #picker-box { width: 76; height: 90%; border: solid $accent; padding: 1 2; }
    #picker-current { height: auto; padding: 0 0 1 0; color: $text-muted; }
    #picker-tree { height: 1fr; }
    #picker-actions { height: auto; padding: 1 0 0 0; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, start: str) -> None:
        super().__init__()
        folder = Path(start) if start and Path(start).is_dir() else Path.cwd()
        self._chosen = str(folder)
        self._start = str(folder)

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="picker-box"):
            yield Label(f"Folder: {self._chosen}", id="picker-current")
            yield DirectoryPicker(self._start, id="picker-tree")
            with Horizontal(id="picker-actions"):
                yield Button("Use this folder", id="picker-use", variant="primary")
                yield Button("Cancel", id="picker-cancel")
        yield Footer()

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._chosen = str(event.path)
        self.query_one("#picker-current", Label).update(f"Folder: {self._chosen}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-use":
            self.dismiss(self._chosen)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class RootNotesScreen(Screen[tuple[str, ...] | None]):
    """Tick the notes a run starts from.

    Dismisses with the ticked notes, or with nothing when cancelled.
    """

    TITLE = "Choose root notes"
    CSS = """
    RootNotesScreen { align: center middle; }
    #roots-box { width: 76; height: 90%; border: solid $accent; padding: 1 2; }
    #roots-empty { height: auto; padding: 0 0 1 0; color: $warning; }
    #roots-list { height: 1fr; }
    #roots-actions { height: auto; padding: 1 0 0 0; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, notes: list[str], selected: tuple[str, ...]) -> None:
        super().__init__()
        self.notes = notes
        self._selected = selected

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="roots-box"):
            if not self.notes:
                yield Label(
                    "No notes in this folder yet - nothing to tick.",
                    id="roots-empty",
                )
            yield SelectionList(
                *[
                    Selection(note, note, note in self._selected)
                    for note in self.notes
                ],
                id="roots-list",
            )
            with Horizontal(id="roots-actions"):
                yield Button("Apply", id="roots-apply", variant="primary")
                yield Button("Cancel", id="roots-cancel")
        yield Footer()

    def shown_notes(self) -> list[str]:
        return list(self.notes)

    def chosen_notes(self) -> list[str]:
        return list(self.query_one("#roots-list", SelectionList).selected)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "roots-apply":
            self.dismiss(tuple(self.chosen_notes()))
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
