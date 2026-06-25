# 🗂️ anki-markdown-importer

[![Python Version](https://img.shields.io/badge/python-%3E%3D%203.13.5-blue.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Package Manager](https://img.shields.io/badge/package%20manager-uv-7a55f8.svg?style=flat-square)](https://github.com/astral-sh/uv)
[![Integration](https://img.shields.io/badge/integration-AnkiConnect-brightgreen.svg?style=flat-square)](https://ankiweb.net/shared/info/2055492159)
[![License](https://img.shields.io/badge/license-MIT-orange.svg?style=flat-square)](#)

A highly robust, obsidian-aware automation tool that seamlessly imports your Markdown notes into Anki flashcards. Unlike traditional static tools, this importer recursively traverses your note tree, resolves wiki-links with full alias support, preserves advanced mathematical equations, and keeps your cards up-to-date in real-time.

---

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| **🔗 Recursive Tree Import** | Supply a few root notes, and the script automatically traces all `[[wiki-links]]` to build and import your complete graph of knowledge. |
| **🔄 Seamless Card Upserting** | Automatically updates existing card backs using AnkiConnect's `updateNote` when `upsert=True` is enabled, avoiding annoying duplicates or missed updates. |
| **🏷️ Dual Tag Extraction** | Extracts tags defined in your YAML frontmatter *and* `#hashtags` from note body text, keeping your Anki database perfectly categorized. |
| **🧮 Native MathJax Support** | Automatically guards LaTeX content (`$` and `$$`) during markdown rendering to prevent Markdown-parser corruption and outputs native Anki MathJax delimiters (`\(` and `\[`). |
| **📊 Dataview Integration** | Dynamically evaluates inline Dataview queries like `="\$"+this.formula+"\$"` and replaces them with corresponding YAML frontmatter property values. |
| **🎭 Functional Wikilinks** | Parses piped links like `[[Target Note \| Custom Display Name]]` into native Obsidian URIs, allowing you to instantly jump back to the original note in Obsidian directly from your Anki reviewer. |
| **🖼️ Image Protection** | Detects local Obsidian image embeds `![[image.png]]` or `![[image.jpg|width]]` and replaces them with clean `*[image_placeholder]*` tags to keep layouts tidy. |
| **🛑 Selective Skipping** | Skip notes you don't want in Anki by simply adding the `not_included` tag to their frontmatter or body. |
| **💡 Callout Integration** | Detects Obsidian callouts (like `> [!tip]`, `> [!warning]`) and styles them into distinctive, left-aligned, high-contrast HTML cards. |
| **🪵 High-Fidelity Logging** | Powered by `loguru`, generates rotation-aware, colorized logging to both standard output and `/logs/anki_importer.log`. |

---

## 🛠️ Prerequisites

Before you run the importer, ensure you have the following setup:

1. **Python 3.13.5+** installed on your system.
2. **Anki** desktop application running locally.
3. The **[AnkiConnect](https://ankiweb.net/shared/info/2055492159)** add-on installed inside Anki (Code: `2055492159`).
4. **`uv`** (astral) package manager installed for fast dependency resolution:
   ```bash
   # Install uv via curl
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   *Alternatively, install via pip:*
   ```bash
   pip install uv
   ```

---

## 🚀 Installation & Setup

1. Clone this repository to your local machine.
2. Install the package and its requirements in a highly-optimized virtual environment using `uv`:
   ```bash
   uv pip install .
   ```

---

## ⚙️ Configuration

Open `main.py` and modify the configuration block inside the `if __name__ == '__main__':` section at the bottom of the file:

```python
# in main.py
DEFAULT_FOLDER_PATH = './vaults/workspace_algebra'  # Absolute or relative path to your Markdown notes directory
DEFAULT_DECK_NAME = "algebra_obsidian"       # Target deck name in Anki (will be created if it doesn't exist)
INITIAL_MD_FILES = ['repaso_algebra']        # Root notes (without the .md extension) to start recursive parsing from
CARD_PREFIX = ''                             # Optional prefix to prepend to all card fronts (e.g. 'Math::')
```

### Parameter Reference

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `folder_path` | `str` | `"./files"` | The directory where all your Obsidian `.md` files reside. |
| `deck_name` | `str` | `"Default"` | The destination deck name in Anki. |
| `initial_md_files` | `list` | `None` | The list of starting markdown files to explore recursively. |
| `upsert` | `bool` | `False` | When `True`, updates existing card backs in Anki if a card with the same front exists. |
| `skip_submission` | `bool` | `False` | If set to `True`, parses and validates cards without posting them to Anki. |
| `card_prefix` | `str` | `""` | A prefix prepended to note titles (e.g., if you want hierarchical naming). |

---

## 💻 Running the Importer

With Anki open and running in the background, execute the script with:

```bash
uv run python main.py
```

### 💡 Example Workflow

1. You have a note named `repaso_algebra.md` in your `./vaults/workspace_algebra` directory containing:
   ```markdown
   ---
   tags: [study, math]
   formula: "e^{i\pi} + 1 = 0"
   ---
   # Algebra Review
   We can analyze this with Euler's identity: `="\$"+this.formula+"\$"`.
   Also look at [[Quadratic Formula|The Quadratic Equation]] for basic solver techniques.
   ```
2. The importer resolves `repaso_algebra.md`, extracts the `study` and `math` tags, replaces the Dataview query with the actual formula `$e^{i\pi} + 1 = 0$`, parses the MathJax block correctly, extracts the `[[Quadratic Formula]]` link to be parsed next, and creates/updates a card in your `algebra_obsidian` deck.
3. The card front is set to `repaso_algebra` and the back renders perfectly formatted MathJax!

---

## 🧪 Running Tests

The test suite runs against isolated, self-contained mock markdown files located under `tests/test_notes/` so it never touches your actual notes.

To run the unit tests:

```bash
uv run python -m unittest discover -s tests
```

---

## 🔍 Troubleshooting

#### ❌ `Cannot connect to AnkiConnect...`
1. Ensure your **Anki** application is active and running.
2. Verify **AnkiConnect** is successfully installed via `Tools -> Add-ons`.
3. If you run custom firewalls, check if port `8765` is accessible. In AnkiConnect config (`Tools -> Add-ons -> AnkiConnect -> Config`), ensure `webBindAddress` is set to `127.0.0.1` and `webCorsOriginList` includes `http://localhost`.

#### ❌ `FileNotFoundError: Folder './vaults/workspace_algebra' does not exist.`
- Double-check that your configured `DEFAULT_FOLDER_PATH` matches the location of your Obsidian vault or folder containing the `.md` notes.
