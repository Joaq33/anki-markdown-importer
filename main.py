import os
import re
import time
from dataclasses import dataclass
from dataclasses import field

import markdown
import requests
import frontmatter
from icecream import ic


@dataclass
class Card:
    front: str = ""
    back: str = ""
    frontmatter: dict[str, list[str]] = None
    raw_content: str = ""
    tags: set[str] = field(default_factory=set)

    def __repr__(self):
        # return f"Card(tags={self.tags}, front={self.front!r}, back={self.back[:20]!r}...)"
        return f"Card(front={self.front!r}, back={self.back[:20]!r}..., tags={self.tags})"


class AnkiHelper:
    not_included_tag = 'not_included'

    def __init__(self, folder_path="./files", deck_name="Default", host='http://localhost', port='8765'):
        self.folder_path = folder_path
        self.deck_name = deck_name
        self.url = host + ':' + port
        self.success_count = 0
        self.failed_count = 0
        self.skipped_count = 0

        self._check_folder_existance()

    def check_anki_connection(self) -> bool:
        """Check if AnkiConnect is available"""
        try:
            payload = {"action": "version", "version": 6}
            response = requests.post(self.url, json=payload)
            result = response.json()
            print(f"AnkiConnect version: {result.get('result', 'Unknown')}")
            return True
        except requests.exceptions.RequestException:
            print("Error: Cannot connect to AnkiConnect. Make sure Anki is running with AnkiConnect add-on installed.")
            return False
        except Exception as e:
            print(f"Unexpected error while checking AnkiConnect: {e}")
            return False

    def post_card_to_deck(self, card: Card) -> bool:
        payload = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": self.deck_name,
                    "modelName": "Basic",
                    "fields": {
                        "Front": card.front,
                        "Back": card.back
                    }
                }
            }
        }

        # return True  # # Placeholder for the actual implementation
        try:
            response = requests.post(self.url, json=payload)
            result = response.json()

            if result.get('error'):
                print(f"Error adding note '{card}': {result['error']}")
                return False
            else:
                print(f"Successfully added note: {card}")
                return True

        except requests.exceptions.RequestException as e:
            print(f"Failed to connect to AnkiConnect: {e}")
            return False

    @staticmethod
    def md_to_html_parser(md_content):
        """Convert markdown content to HTML"""
        return markdown.markdown(md_content)

    def create_card(self, filename: str, content: str) -> Card:
        card = Card()

        card.frontmatter, card.raw_content = self.separate_frontmatter(content)

        tags_frontmatter = self.extract_tags_frontmatter(card.frontmatter)
        if tags_frontmatter:
            card.tags.update(tags_frontmatter)

        tags_raw_content = self.extract_tags_raw_content(card.raw_content)
        if tags_raw_content:
            card.tags.update(tags_raw_content)

        if not card.tags:
            card.tags.add('default')
        ic(card.tags)

        if self.not_included_tag in card.tags:
            print(f"Skipping file '{filename}' due to '{self.not_included_tag}' tag.")
            return 'SKIPPED'

        card.front = os.path.splitext(filename)[0]  # Use filename without extension as front of card
        card.back = self.md_to_html_parser(content)  # Convert markdown content to HTML for the back of the card
        if self.post_card_to_deck(card=card):
            return 'SUCCESS'
        else:
            return 'FAILED'

    def run(self) -> None:
        """Process all markdown files in the specified folder"""

        # Get all markdown files
        md_files = self.get_all_md_in_folder(self.folder_path)

        if not md_files:
            print(f"No markdown files found in '{self.folder_path}'")
            return

        print(f"Found {len(md_files)} markdown files to process...")

        # success_count = 0
        # failed_count = 0
        # skipped_count = 0

        for filename in md_files:
            file_path = os.path.join(self.folder_path, filename)

            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()

                response = self.create_card(filename, content)
                match response:
                    case 'SUCCESS':
                        self.success_count += 1
                    case 'FAILED':
                        self.failed_count += 1
                    case 'SKIPPED':
                        self.skipped_count += 1


                # Small delay to avoid overwhelming AnkiConnect
                time.sleep(0.1)

            except Exception as e:
                print(f"Error processing file '{filename}': {e}")
                failed_count += 1

        print(f"\nProcessing complete!")
        print(f"Successfully added: {success_count} notes")
        print(f"Failed: {failed_count} notes")
        print(f"Skipped: {skipped_count} notes")

    def _check_folder_existance(self):
        # Check if folder exists
        if not os.path.exists(self.folder_path):
            # print(f"Error: Folder '{self.folder_path}' does not exist.")
            raise FileNotFoundError(f"Folder '{self.folder_path}' does not exist.")

    @staticmethod
    def get_all_md_in_folder(folder_path) -> list[str]:
        """Get all markdown files in the specified folder"""
        return [f for f in os.listdir(folder_path) if f.lower().endswith(('.md', '.markdown'))]

    def extract_tags_raw_content(self, content: str) -> list[str]:
        """Extract tags from the markdown content"""
        # This is a placeholder implementation. You can customize it based on your tagging convention.
        return re.findall(r'#(\w+)', content)

    def separate_frontmatter(self, content: str) -> tuple[str, str]:
        return frontmatter.parse(content)

    @staticmethod
    def extract_tags_frontmatter(frontmatter_parsed):
        return frontmatter_parsed['tags'] if 'tags' in frontmatter_parsed else None


if __name__ == '__main__':
    # Configuration
    default_folder = './files2'
    # FOLDER_PATH = input(
    #     f"Enter the path to your markdown folder (or press enter to use '{default_folder}'): ").strip() or default_folder
    default_deck = "nuevas_notas2"
    # DECK_NAME = input(f"Enter the Anki deck name (or press Enter for '{default_deck}'): ").strip() or default_deck

    FOLDER_PATH = default_folder
    DECK_NAME = default_deck

    ah = AnkiHelper(folder_path=FOLDER_PATH, deck_name=DECK_NAME)

    # Check AnkiConnect connection
    if not ah.check_anki_connection():
        raise ConnectionError(
            "Failed to connect to AnkiConnect. Please ensure Anki is running with the AnkiConnect add-on installed.")

    # Process the folder
    ah.run()
