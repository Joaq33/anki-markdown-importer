"""The screens the app can show, beyond the one it starts on."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Switch

from ..import_run import RunSettings, parse_root_notes


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

    def __init__(self, settings: RunSettings) -> None:
        super().__init__()
        self.settings = settings

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-box"):
            with Horizontal():
                yield Label("Vault folder")
                yield Input(self.settings.vault_path, id="config-vault")
            with Horizontal():
                yield Label("Deck name")
                yield Input(self.settings.deck_name, id="config-deck")
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
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)