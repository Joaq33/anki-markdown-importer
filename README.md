
# anki-markdown-importer

> A powerful tool to seamlessly convert your Obsidian-style markdown notes into Anki flashcards, including linked notes.

---

## Features

-   **Recursive Note Processing:** Starts from a root note and automatically follows all `[[wiki-style]]` links to import a complete tree of knowledge.
-   **Markdown to HTML:** Converts your markdown content to HTML for the "Back" of your Anki cards.
-   **Tag Management:** Automatically extracts tags from your note's frontmatter and from `#hastags` in the content.
-   **Frontmatter-Aware:** Parses YAML frontmatter in your markdown files to extract metadata.
-   **Selective Import:** Skip specific notes by adding the `not_included` tag.
-   **Image Placeholders:** Identifies image links and replaces them with a simple placeholder in your Anki cards.
-   **Direct Anki Integration:** Uses the AnkiConnect addon to add notes directly to your specified deck.
-   **Robust Logging:** Keeps a detailed log of all operations for easy debugging.
-   **Case-Insensitive Linking:** Finds your linked notes even if the link's capitalization doesn't match the filename.

---

## How It Works

The script begins with a "root" note that you specify. It reads the content, creates an Anki card from it, and then scans the note for any `[[links]]` to other notes. It then recursively processes each of those linked notes, and any notes linked from them, and so on. This allows you to import an entire, interconnected section of your notes into Anki in one go.

---

## Prerequisites

Before you begin, ensure you have the following set up:

1.  **Python >=3.13.5**
2.  **Anki** installed and running.
3.  The **AnkiConnect** addon installed in Anki.
4.  **`uv`**, the Python package installer. If you don't have it, you can install it with:
    ```bash
    pip install uv
    ```
    Or with curl:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

---

## Installation

Clone this repository and then install the required Python packages using `uv`:

```bash
uv pip install .
```

---

## Usage

1.  **Configure the script:**

    Open the `main.py` file and edit the configuration variables at the bottom of the file, inside the `if __name__ == '__main__':` block.

    -   `INITIAL_MD_FILES`: A list of root notes to start processing from (without the `.md` extension).
    -   `DEFAULT_FOLDER_PATH`: The path to the folder where your markdown notes are stored.
    -   `DEFAULT_DECK_NAME`: The name of the Anki deck you want to add the cards to.

    **Example Configuration:**
    ```python
    # in main.py
    INITIAL_MD_FILES = ['My Root Note']
    DEFAULT_FOLDER_PATH = './files'
    DEFAULT_DECK_NAME = "My Anki Deck"
    ```

2.  **Run the importer:**

    Execute the script from your terminal using `uv`:

    ```bash
    uv run python main.py
    ```

---
