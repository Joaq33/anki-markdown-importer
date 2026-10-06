"""Entry point for the Obsidian-to-Anki importer.

Running this launches the terminal UI. The old scripted entry point is still
available as `AnkiHelper` for anyone driving an import from Python.
"""

import sys

from anki_importer import Card, ImportRun, RunSettings
from anki_importer.facade import AnkiHelper
from anki_importer.logging_setup import configure_file_logging

__all__ = ["AnkiHelper", "Card", "ImportRun", "RunSettings", "main", "run_import"]


def run_import(settings: RunSettings) -> None:
    """Import from the command line, without a UI."""
    from anki_importer.gateway import AnkiConnectGateway

    run = ImportRun(settings)
    gateway = AnkiConnectGateway()
    for _ in run.build_cards():
        pass
    for event in run.submit(gateway):
        pass
    for _ in run.resolve_links(gateway):
        pass


def main() -> int:
    from anki_importer.tui.app import AnkiImporterApp

    configure_file_logging()
    AnkiImporterApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())