"""The pre-TUI entry point, kept working on top of the new core.

`AnkiHelper` is the facade the original `main.py` exposed. It now composes the
import core and the AnkiConnect gateway instead of doing the work itself, so the
old scripted entry point and its tests behave exactly as they did.
"""

from typing import Any

from loguru import logger as log

from .card import Card
from .card_builder import CardBuilder
from .gateway import AnkiConnectGateway, SubmitOutcome
from .import_run import (
    CardBuilt,
    ImportRun,
    LinkProgress,
    LinksResolved,
    NoteDiscovered,
    NoteUnreadable,
    RunSettings,
)
from .notes import FolderNoteSource

SUPPORTED_MODES = frozenset({"tree_from_flat_folder"})

OUTCOME_NAMES = {
    SubmitOutcome.ADDED: "SUCCESS",
    SubmitOutcome.UPDATED: "SUCCESS",
    SubmitOutcome.SKIPPED: "SKIPPED",
    SubmitOutcome.FAILED: "FAILED",
}


class AnkiHelper:
    """Imports a folder of notes into one Anki deck, the way it always has."""

    not_included_tag = "not_included"

    def __init__(
        self,
        folder_path: str = "./files",
        deck_name: str = "Default",
        host: str = "http://localhost",
        port: str = "8765",
        skip_submission: bool = False,
        initial_md_files: list[str] | None = None,
        mode: str = "tree_from_flat_folder",
        card_prefix: str = "",
        upsert: bool = False,
        generate_links: bool = True,
    ) -> None:
        if mode not in SUPPORTED_MODES:
            raise NotImplementedError(
                f"Invalid mode '{mode}' not implemented. "
                f"Supported modes: {', '.join(sorted(SUPPORTED_MODES))}."
            )
        self.mode = mode
        self.folder_path = folder_path
        self.deck_name = deck_name
        self.skip_submission = skip_submission
        self.card_prefix = card_prefix
        self.upsert = upsert
        self.generate_links = generate_links
        self.gateway = AnkiConnectGateway(host=host, port=port)

        self.success_count = 0
        self.failed_count = 0
        self.skipped_count = 0

        self._builder = CardBuilder(not_included_tag=self.not_included_tag)
        self._source = FolderNoteSource(folder_path)
        self.run_state = ImportRun(
            RunSettings(
                vault_path=folder_path,
                deck_name=deck_name,
                root_notes=tuple(initial_md_files or ()),
                card_prefix=card_prefix,
                upsert=upsert,
                generate_links=generate_links,
            ),
            source=self._source,
            builder=self._builder,
        )

    @property
    def md_files_tracked(self) -> set[str]:
        """Every note this helper covers: the starting files plus what they led to.

        The starting files count as tracked from the outset, which is what the
        original helper reported before a run began.
        """
        return set(self.run_state.settings.root_notes) | self.run_state.discovery.tracked

    @property
    def cards(self) -> list[Card]:
        return self.run_state.cards

    def check_anki_connection(self) -> bool:
        if self.gateway.is_available():
            log.info("AnkiConnect is available.")
            return True
        log.error(
            "Cannot connect to AnkiConnect. Make sure Anki is running with "
            "the AnkiConnect add-on installed."
        )
        return False

    def read_file_case_insensitive_simple(self, filename: str, directory: str) -> str:
        return FolderNoteSource(directory).read(filename)

    def create_card(self, filename: str, content: str) -> Card:
        return self._builder.build(
            filename,
            content,
            card_prefix=self.card_prefix,
            generate_links=self.generate_links,
        )

    @staticmethod
    def md_to_html_parser(md_content: str) -> str:
        return CardBuilder.markdown_to_html(md_content)

    def extract_and_format_callouts(self, content: str) -> str:
        return self._builder.format_callouts(content)

    def extract_and_replace_formula_property(
        self, content: str, frontmatter: dict[str, Any]
    ) -> str:
        return self._builder.replace_formula_property(content, frontmatter)

    def process_card_submission(self, card: Card) -> str:
        if card.should_skip:
            log.info(f"Skipping card '{card.front}' due to 'should_skip' flag.")
            return "SKIPPED"
        if self.skip_submission:
            log.info(
                f"Skipping submission for card '{card.front}' due to "
                "'skip_submission' flag."
            )
            return "SKIPPED"
        return self.post_card_to_deck(card)

    def post_card_to_deck(self, card: Card) -> str:
        if self.upsert:
            note_id = self.gateway.note_id_for_front(self.deck_name, card.front)
            if note_id is not None:
                outcome = self.gateway.update_note(self.deck_name, card, note_id)
                return OUTCOME_NAMES[outcome]
        return OUTCOME_NAMES[self.gateway.add_note(self.deck_name, card)]

    def run(self) -> None:
        """Discover every note reachable from the initial files and import them."""
        log.info(f"Starting to process markdown files in folder: {self.folder_path}")
        log.info(f"Using Anki deck: {self.deck_name}")
        log.info(f"Link generation enabled: {self.generate_links}")

        for event in self.run_state.build_cards():
            match event:
                case NoteDiscovered(name):
                    log.info(f"Added new markdown file for processing: {name}")
                case NoteUnreadable(name):
                    log.error(f"File '{name}' not found. Skipping...")
                case CardBuilt(card):
                    if card.should_skip:
                        log.info(
                            f"Skipping file '{card.front}' due to "
                            f"'{self.not_included_tag}' tag."
                        )
                    outcome = self.process_card_submission(card)
                    self._count(outcome)

        if not self.skip_submission and self.generate_links:
            for link_event in self.run_state.resolve_links(self.gateway):
                if isinstance(link_event, LinksResolved):
                    log.info(
                        f"Link resolution complete: {link_event.resolution.resolved} "
                        f"resolved, {link_event.resolution.unresolved} unresolved."
                    )
                elif isinstance(link_event, LinkProgress):
                    log.debug(
                        f"Link resolution: {link_event.resolved} resolved, "
                        f"{link_event.unresolved} unresolved."
                    )

        log.info("\nProcessing complete!")
        log.info(f"Successfully added: {self.success_count} notes")
        log.info(f"Failed: {self.failed_count} notes")
        log.info(f"Skipped: {self.skipped_count} notes")

    def _count(self, outcome: str) -> None:
        match outcome:
            case "SUCCESS":
                self.success_count += 1
            case "FAILED":
                self.failed_count += 1
            case "SKIPPED":
                self.skipped_count += 1