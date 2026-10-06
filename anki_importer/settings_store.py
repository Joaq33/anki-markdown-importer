"""Saving settings to disk and reading them back.

The file is TOML, read with the standard library and written by hand so the
tool needs no extra dependency. The writer only knows this one shape: strings
quoted the way JSON quotes them (valid TOML), booleans lowercase, root notes as
a list of strings. Anything hand-edited outside that shape is the reader's
problem, and it says so.
"""

import json
import tomllib
from pathlib import Path

from .import_run import RunSettings

DEFAULT_FILE_NAME = "anki-importer.toml"


def load_settings(path: str | Path) -> RunSettings:
    """Read the settings at `path`, or the defaults when nothing is there yet."""
    file = Path(path)
    if not file.exists():
        return RunSettings(vault_path="")
    with open(file, "rb") as handle:
        try:
            values = tomllib.load(handle)
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"Could not read the settings file {file}: {error}") from error
    return RunSettings(
        vault_path=str(values.get("vault_path", "")),
        deck_name=str(values.get("deck_name", "Default")),
        root_notes=tuple(str(note) for note in values.get("root_notes", ())),
        card_prefix=str(values.get("card_prefix", "")),
        upsert=bool(values.get("upsert", False)),
        generate_links=bool(values.get("generate_links", True)),
        throttle_seconds=float(values.get("throttle_seconds", 0.1)),
    )


def save_settings(settings: RunSettings, path: str | Path) -> None:
    """Write the settings to `path` in a form a person can read and edit."""
    file = Path(path)
    notes = ", ".join(json.dumps(note) for note in settings.root_notes)
    text = (
        "# Settings for the Anki importer. Safe to edit by hand.\n"
        f"vault_path = {json.dumps(settings.vault_path)}\n"
        f'deck_name = {json.dumps(settings.deck_name)}\n'
        f"root_notes = [{notes}]\n"
        f'card_prefix = {json.dumps(settings.card_prefix)}\n'
        f"upsert = {'true' if settings.upsert else 'false'}\n"
        f"generate_links = {'true' if settings.generate_links else 'false'}\n"
        f"throttle_seconds = {settings.throttle_seconds}\n"
    )
    file.write_text(text, encoding="utf-8")