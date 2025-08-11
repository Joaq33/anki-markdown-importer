import os
import re
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Optional

import frontmatter
import markdown
import requests
from loguru import logger as log
import sys

# from prueba_anki import deck_name

log.remove()
log.add(sys.stdout, level="INFO")

# Max log size is 2.55 MB for pycharm read support, and it will be rotated after that.
log.add(sink='./logs/anki_importer.log', level='DEBUG', rotation='2.55 MB', retention='10 days', )


@dataclass
class Card:
    front: str = ""
    back: str = ""
    frontmatter: dict[str, list[str]] = None
    staged_content: str = ""
    should_skip: bool = False
    tags: set[str] = field(default_factory=set)

    def __repr__(self):
        # return f"Card(tags={self.tags}, front={self.front!r}, back={self.back[:20]!r}...)"
        return f"Card(front={self.front!r}, back={self.back[:20]!r}..., tags={self.tags})"


class AnkiHelper:
    not_included_tag = 'not_included'

    def __init__(self, folder_path="./files", deck_name="Default", host='http://localhost', port='8765',
                 skip_submission=False, initial_md_files=None, mode='tree_from_flat_folder', card_prefix='',
                 upsert=False):
        # self.next_md_files = initial_md_files
        # self.new_md_files = initial_md_files
        self.folder_path = folder_path
        self.deck_name = deck_name
        self.url = host + ':' + port
        self.success_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.skip_submission = skip_submission  # Feature flag to skip submission
        # self.obsidian_links = set()  # obsidian links to other notes
        self.mode = mode
        self.card_prefix = card_prefix
        self.upsert = upsert

        match self.mode:
            case 'tree_from_flat_folder':
                self.md_files_tracked = set()  # files tracked to avoid duplicates
                self.next_md_files = []  # next markdown files to be processed helper
                try:
                    # self.update_md_files_trackers(initial_md_files) if initial_md_files else None
                    for filename in initial_md_files:
                        self.update_md_files_trackers(filename)
                except Exception as e:
                    log.exception(f"Error initializing markdown files trackers: {e}")
                    raise e
                self.new_md_files = self.next_md_files
            case _:
                raise NotImplementedError(
                    f"Invalid mode '{mode}' not implemented. Supported modes: 'tree_from_flat_folder'.")

        self._check_folder_existance()  # todo check file existence in the folder_path

    def update_md_files_trackers(self, filename: str):
        """
        Update the tracker for markdown files to avoid duplicates and to manage the next files to process.
        """
        assert filename is not None, "filename must be provided"
        assert isinstance(filename, str), "filename must be a string"
        # assert filename.endswith('.md') or filename.endswith('.markdown'), "filename must be a markdown file"

        # Only execute if mode is recursive
        if self.mode in {'flat', }:
            log.debug("Flat mode is not supported for updating markdown files trackers.")
            return

        if filename not in self.md_files_tracked:
            self.md_files_tracked.add(filename)
            self.next_md_files.append(filename)
            log.info(f"Added new markdown file for processing: {filename}")
        else:
            log.debug(f"Markdown file '{filename}' is already tracked. No action taken.")

    def check_anki_connection(self) -> bool:
        """Check if AnkiConnect is available"""
        try:
            payload = {"action": "version", "version": 6}
            response = requests.post(self.url, json=payload)
            result = response.json()
            log.info(f"AnkiConnect version: {result.get('result', 'Unknown')}")
            return True
        except requests.exceptions.RequestException:
            log.error("Cannot connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on installed.")
            return False
        except Exception as e:
            log.exception(f"Unexpected error while checking AnkiConnect: {e}")
            return False

    def process_card_submission(self, card: Card) -> str:
        """
        Process the card submission to Anki.
        """
        log.debug(f"Processing card: {card}")
        if card.should_skip:
            log.info(f"Skipping card '{card.front}' due to 'should_skip' flag.")
            return 'SKIPPED'

        if self.skip_submission:
            log.info(f"Skipping submission for card '{card.front}' due to 'skip_submission' flag.")
            return 'SKIPPED'
        return self.post_card_to_deck_v2(card)

    # def post_card_to_deck(self, card: Card) -> str:
    #     """
    #     Post a card to the Anki deck using AnkiConnect API.
    #     :param card: Card object containing front, back, tags, etc.
    #     :return: 'SUCCESS', 'FAILED', or 'SKIPPED' based on the result of the operation.
    #     """
    #     payload = {
    #         "action": "addNote",
    #         "version": 6,
    #         "params": {
    #             "note": {
    #                 "deckName": self.deck_name,
    #                 "modelName": "Basic",
    #                 "fields": {
    #                     "Front": card.front,
    #                     "Back": card.back
    #                 },
    #                 "tags": list(card.tags) if card.tags else [],
    #             }
    #         }
    #     }
    #
    #     try:
    #         response = requests.post(self.url, json=payload)
    #         result = response.json()
    #
    #         if result.get('error'):
    #             if result['error'] == "cannot create note because it is a duplicate":
    #                 log.warning(f"Note '{card.front}' already exists in the deck. Skipping duplicate.")
    #                 return 'SKIPPED'
    #             log.error(f"Error adding note '{card}': {result['error']}")
    #             return 'FAILED'
    #         else:
    #             log.info(f"Successfully added note: {card}")
    #             return 'SUCCESS'
    #
    #     except requests.exceptions.RequestException as e:
    #         log.exception(f"Failed to connect to AnkiConnect: {e}")
    #         return 'FAILED'

    def check_card_existence(self, filename: str, card: Card) -> Optional[str]:
        """
        Check if a card with the given front already exists in the Anki deck.
        """
        payload = {
            "action": "findNotes",
            "version": 6,
            "params": {"query": f"deck:{self.deck_name} front:\"{card.front}\""}
        }
        try:
            response = requests.post(self.url, json=payload)
            result = response.json()
            if result.get('error'):
                log.error(f"Error checking card existence for '{card.front}': {result['error']}")
                raise Exception(f"Error checking card existence: {result['error']}")
            if result['result']:
                match len(result['result']):
                    case 0:
                        log.debug(f"No existing card found for front '{card.front}'.")
                        return None  # No existing card found
                    case 1:
                        log.debug(f"Found existing card ID: {result['result'][0]} for front '{card.front}'.")
                        return result['result'][0]  # Return the existing card ID
                    case _:
                        log.warning(f"Multiple cards found with the same front '{card.front}'. Returning first match.")
                        return result['result'][0]  # Return the first match
            log.debug(f"No result found for front '{card.front}' in deck '{self.deck_name}': {result}.")
            return None  # No result found
        except Exception as e:
            log.exception(f"Error checking card existence for '{card.front}': {e}")
            return None

    def post_card_to_deck_v2(self, card: Card) -> str:
        """
        Post a card to the Anki deck using AnkiConnect API.
        :param card: Card object containing front, back, tags, etc.
        :return: 'SUCCESS', 'FAILED', or 'SKIPPED' based on the result of the operation.
        """
        note_payload_field = {
            "deckName": self.deck_name,
            "modelName": "Basic",
            "fields": {
                "Front": card.front,
                "Back": card.back
            },
            "tags": list(card.tags) if card.tags else [],
        }

        action = "addNote"
        existing_card_id: Optional[str] = None
        if self.upsert:
            # Check card existence
            existing_card_id = self.check_card_existence(card.front, card)
            if existing_card_id:
                note_payload_field['id'] = existing_card_id
                del note_payload_field['fields']['Front']  # Do not update the front field
                action = "updateNote"

        payload = {
            "action": action,
            "version": 6,
            "params": {
                "note": note_payload_field
            }
        }

        try:
            response = requests.post(self.url, json=payload)
            result = response.json()

            if result.get('error'):
                if result['error'] == "cannot create note because it is a duplicate":
                    log.warning(f"Note '{card.front}' already exists in another deck. Skipping.")
                    return 'SKIPPED'
                log.error(f"Error adding note '{card}': {result['error']}")
                return 'FAILED'
            else:
                if existing_card_id:
                    log.info(f"Successfully updated note: {card}")
                else:
                    log.info(f"Successfully added note: {card}")
                return 'SUCCESS'

        except requests.exceptions.RequestException as e:
            log.exception(f"Failed to connect to AnkiConnect: {e}")
            return 'FAILED'

    @staticmethod
    def md_to_html_parser(md_content):
        """Convert markdown content to HTML"""

        # fix ][ line breaks
        md_content = md_content.replace('\n', '<br>')

        return markdown.markdown(md_content)

    def create_card(self, filename: str, content: str) -> Card:
        card = Card()

        card.frontmatter, card.staged_content = self.separate_frontmatter(content)

        tags_frontmatter = self.extract_tags_frontmatter(card.frontmatter)
        if tags_frontmatter:
            card.tags.update(tags_frontmatter)

        tags_raw_content = self.extract_tags_raw_content(card.staged_content)
        if tags_raw_content:
            card.tags.update(tags_raw_content)

        # if not card.tags:
        #     card.tags.add('default')

        if self.not_included_tag in card.tags:
            log.info(f"Skipping file '{filename}' due to '{self.not_included_tag}' tag.")
            card.front = self.card_prefix + filename
            card.back = "This note is skipped due to the 'not_included' tag."
            card.should_skip = True
            return card

        card.front = self.card_prefix + os.path.splitext(filename)[0]  # Use filename without extension as front of card

        card.staged_content = self.extract_and_replace_images(card.staged_content)
        card.staged_content = self.extract_and_replace_obsidian_links(card.staged_content)

        card.back = self.md_to_html_parser(
            card.staged_content)  # Convert markdown content to HTML for the back of the card
        return card

    def read_file_case_insensitive_simple(self, filename: str, directory: str) -> Optional[
        str]:
        """
        Simpler version using os.listdir() - good for smaller directories.
        """
        try:
            files = os.listdir(directory)
            filename_lower = filename.lower()
            log.debug(f'files in directory {directory}:')
            log.debug(files)
            log.debug(f'Looking for file: {filename_lower}')
            for file in files:
                name, ext = os.path.splitext(file)

                if ext in ('.md', '.markdown') and name.lower() == filename_lower:
                    filepath = os.path.join(directory, file)
                    if os.path.isfile(filepath):
                        with open(filepath, 'r', encoding="utf-8") as f:
                            return f.read()
                    else:
                        raise IOError(f"File '{file}' is not a regular file.")
        except (OSError, IOError) as e:
            raise IOError(f"Error accessing directory or file: {e}")
        raise FileNotFoundError(
            f"Markdown file '{filename}' not found in directory '{directory}'. Please check the filename and directory path.")

    def run(self) -> None:
        """Process all markdown files in the specified folder"""

        log.info(
            f"Starting to process markdown files in folder: {self.folder_path}")  # todo change to reference initial files instead of folder path
        log.info(f"Using Anki deck: {self.deck_name}")

        # # Get all markdown files using folder_path
        # self.new_md_files = self.get_all_md_in_folder()

        # self.new_md_files

        # iterate if self.new_md_files is not empty
        while self.new_md_files:
            self.next_md_files = []
            for filename in self.new_md_files:
                file_path = os.path.join(self.folder_path, f"{filename}.md" if (
                        not filename.endswith('.md') or
                        filename.endswith('.markdown'))
                else filename)  # todo prevent duplicates due to .md extension. P. e. if file is already .md, do not add it again

                try:
                    try:
                        # Read file content
                        # with open(file_path, 'r', encoding='utf-8') as file:
                        #     content = file.read()
                        content = self.read_file_case_insensitive_simple(filename, self.folder_path)
                    except FileNotFoundError:
                        log.error(f"File '{file_path}' not found. Skipping...")
                        self.failed_count += 1
                        continue

                    card = self.create_card(filename, content)

                    response = self.process_card_submission(card)

                    match response:
                        case 'SUCCESS':
                            self.success_count += 1
                        case 'FAILED':
                            self.failed_count += 1
                        case 'SKIPPED':
                            self.skipped_count += 1

                    # Small delay to avoid overwhelming AnkiConnect
                    if not self.skip_submission:
                        time.sleep(0.1)

                except Exception as e:
                    log.exception(f"Error processing file '{filename}': {e}")
                    self.failed_count += 1
            self.new_md_files = self.next_md_files  # Update the list for the next iteration

        log.info(f"\nProcessing complete!")
        log.info(f"Successfully added: {self.success_count} notes")
        log.info(f"Failed: {self.failed_count} notes")
        log.info(f"Skipped: {self.skipped_count} notes")

    def _check_folder_existance(self):
        # Check if folder exists
        if not os.path.exists(self.folder_path):
            # print(f"Error: Folder '{self.folder_path}' does not exist.")
            raise FileNotFoundError(f"Folder '{self.folder_path}' does not exist.")

    @staticmethod
    def _get_all_md_in_folder(folder_path) -> list[str]:
        """Get all markdown files in the specified folder"""
        return [f for f in os.listdir(folder_path) if f.lower().endswith(('.md', '.markdown'))]

    def extract_tags_raw_content(self, content: str) -> list[str]:
        """Extract tags from the markdown content"""
        # This is a placeholder implementation. You can customize it based on your tagging convention.
        return re.findall(r'#(\w+)', content)

    def separate_frontmatter(self, content: str) -> tuple[str, str]:
        return frontmatter.parse(content)

    @staticmethod
    def extract_tags_frontmatter(frontmatter_parsed: dict) -> list[str] | None:
        return frontmatter_parsed['tags'] if 'tags' in frontmatter_parsed else None

    def extract_and_replace_obsidian_links(self, content: str) -> str:
        obsidian_link_pattern = r'\[\[([^\]]+)\]\]'

        def _extract_and_replace_helper(match):
            full_match = match.group(1)
            match_split = full_match.split('|')
            cleaned_match = match_split[0].strip()
            alias_match = match_split[1].strip() if len(match_split) > 1 else cleaned_match

            # Add the actual link to the set
            # self.obsidian_links.add(cleaned_match)
            self.update_md_files_trackers(cleaned_match)

            # Return the alias to replace the original match with an html underline
            return f"<ins>{alias_match}</ins>"

        # Single pass through the content - O(n)
        content = re.sub(obsidian_link_pattern, _extract_and_replace_helper, content)

        # log.info(f"Found Obsidian links: {self.obsidian_links}")
        log.debug(f"Content modified to remove Obsidian links: {content[:100]}...")  # Log first 100 characters

        # Keep only the first part of the content
        content = content.split('\n---\n', 1)[0]
        return content

    def extract_and_replace_images(self, staged_content: str) -> str:
        """
        placeholder for image extraction and replacement
        extract all images in the content, it should be in the format ![alt text](image_path)
        """
        # Regex pattern to match image links with valid extensions
        image_pattern = r'!\[\[([^|\]]+\.(?:png|jpg|jpeg|gif|bmp|svg|webp|tiff|tif|ico))(?:\|[^\]]*)?\]\]'

        staged_content = re.sub(image_pattern, '*__[image_placeholder]__*', staged_content)
        return staged_content

    def get_all_md_in_folder(self):
        tmp = self._get_all_md_in_folder(self.folder_path)

        if not tmp:
            log.warning(f"No markdown files found in '{self.folder_path}'")
            return []

        log.info(f"Found {len(tmp)} markdown files to process...")
        return tmp


if __name__ == '__main__':
    log.info("Starting Anki Importer...")
    DEFAULT_FOLDER_PATH = './workspace'
    DEFAULT_DECK_NAME = "fabric_data_engineer"
    INITIAL_MD_FILES = ['Microsoft Fabric Data Engineer']  # Placeholder for initial markdown files, can be set later

    # Configuration

    # FOLDER_PATH = input(
    #     f"Enter the path to your markdown folder (or press enter to use '{default_folder}'): ").strip() or default_folder
    # DECK_NAME = input(f"Enter the Anki deck name (or press Enter for '{DEFAULT_DECK}'): ").strip() or DEFAULT_DECK

    FOLDER_PATH = DEFAULT_FOLDER_PATH
    DECK_NAME = DEFAULT_DECK_NAME
    ah = AnkiHelper(folder_path=FOLDER_PATH, deck_name=DECK_NAME, skip_submission=False,
                    initial_md_files=INITIAL_MD_FILES, card_prefix='', upsert=True)

    # Check AnkiConnect connection
    if not ah.check_anki_connection():
        raise ConnectionError(
            "Failed to connect to AnkiConnect. Please ensure Anki is running with the AnkiConnect add-on installed.")

    # Process the folder
    ah.run()
    log.success('Finished processing markdown files.')
