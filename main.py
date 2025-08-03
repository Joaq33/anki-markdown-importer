import os
import time
from dataclasses import dataclass

import markdown
import requests


@dataclass
class Card:
    front: str = ""
    back: str = ""

    def __repr__(self):
        return f"Card(front={self.front!r}, back={self.back[:20]!r}...)"


class AnkiHelper:

    def __init__(self, folder_path="./files", deck_name="Default", host='http://localhost', port='8765'):
        self.folder_path = folder_path
        self.deck_name = deck_name
        self.url = host + ':' + port

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

    def run(self) -> None:
        """Process all markdown files in the specified folder"""


        # Get all markdown files
        md_files = self.get_all_md_in_folder(self.folder_path)

        if not md_files:
            print(f"No markdown files found in '{self.folder_path}'")
            return

        print(f"Found {len(md_files)} markdown files to process...")

        success_count = 0
        failed_count = 0

        for filename in md_files:
            file_path = os.path.join(self.folder_path, filename)

            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()

                card = Card()

                card.front = os.path.splitext(filename)[0]  # Use filename without extension as front of card
                card.back = self.md_to_html_parser(content)  # Convert markdown content to HTML for the back of the card

                if self.post_card_to_deck(card=card):
                    success_count += 1
                else:
                    failed_count += 1

                # Small delay to avoid overwhelming AnkiConnect
                time.sleep(0.1)

            except Exception as e:
                print(f"Error processing file '{filename}': {e}")
                failed_count += 1

        print(f"\nProcessing complete!")
        print(f"Successfully added: {success_count} notes")
        print(f"Failed: {failed_count} notes")

    def _check_folder_existance(self):
        # Check if folder exists
        if not os.path.exists(self.folder_path):
            # print(f"Error: Folder '{self.folder_path}' does not exist.")
            raise FileNotFoundError(f"Folder '{self.folder_path}' does not exist.")

    @staticmethod
    def get_all_md_in_folder(folder_path) -> list[str]:
        """Get all markdown files in the specified folder"""
        return [f for f in os.listdir(folder_path) if f.lower().endswith(('.md', '.markdown'))]


if __name__ == '__main__':
    # Configuration
    FOLDER_PATH = input("Enter the path to your markdown folder: ").strip() or 'files2'
    DECK_NAME = input("Enter the Anki deck name (or press Enter for 'D'): ").strip() or "nuevas_notas2"

    ah = AnkiHelper(folder_path=FOLDER_PATH, deck_name=DECK_NAME)
    # Check AnkiConnect connection
    if not ah.check_anki_connection():
        exit(1)

    # Process the folder
    ah.run()
