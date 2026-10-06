"""The app's widgets."""

from dataclasses import dataclass

from textual.widgets import DataTable, RichLog, Static

from ..card import Card
from ..import_run import RunSummary


@dataclass(frozen=True)
class CardRow:
    """One discovered card, as the table shows it."""

    front: str
    tags: str
    skipped: bool

    @classmethod
    def of(cls, card: Card) -> "CardRow":
        return cls(
            front=card.front,
            tags=", ".join(sorted(card.tags)),
            skipped=card.should_skip,
        )

    @property
    def status(self) -> str:
        return "skip" if self.skipped else "import"


class CardTable(DataTable[str]):
    """The notes this run covers, one row each."""

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows: dict[int, CardRow] = {}

    def on_mount(self) -> None:
        self.add_column("Front", key="front")
        self.add_column("Tags", key="tags")
        self.add_column("Status", key="status")
        self.cursor_type = "row"
        self.zebra_stripes = True

    @property
    def fronts(self) -> list[str]:
        """The fronts listed, in the order they were found."""
        return [row.front for row in self._rows.values()]

    def row(self, index: int) -> CardRow:
        return self._rows[index]

    def highlighted_index(self) -> int | None:
        """Which card the cursor is on, if the table lists anything."""
        if not self._rows:
            return None
        return list(self._rows)[self.cursor_row]

    def add_card(self, card: Card) -> CardRow:
        """Append a card at the end, keeping its position stable for edits."""
        index = len(self._rows)
        row = CardRow.of(card)
        self._rows[index] = row
        self.add_row(row.front, row.tags, row.status, key=str(index))
        return row

    def replace_at(self, index: int, card: Card) -> CardRow:
        """Show a card's new contents in its own row."""
        row = CardRow.of(card)
        self._rows[index] = row
        key = str(index)
        self.update_cell(key, "front", row.front)
        self.update_cell(key, "tags", row.tags)
        self.update_cell(key, "status", row.status)
        return row

    def clear_cards(self) -> None:
        self._rows.clear()
        self.clear()


class NoticeBar(Static):
    """One line saying where the app is, plus any problems worth knowing."""

    def __init__(self, notice: str = "", id: str | None = None) -> None:
        super().__init__(notice, id=id)
        self.notice = notice
        self.problems: list[str] = []

    def show(self, notice: str) -> None:
        self.problems = []
        self._set(notice)

    def report(self, notice: str, problems: list[str] | None = None) -> None:
        """Say where we are, and what went wrong if anything did."""
        self.problems = list(problems or [])
        text = notice
        if self.problems:
            text = f"{notice} - " + "; ".join(self.problems)
        self._set(text)

    def _set(self, text: str) -> None:
        self.notice = text
        self.update(text)

class CountBar(Static):
    """The running tally of what a run has done so far."""

    def __init__(self, id: str | None = None) -> None:
        super().__init__("", id=id)
        self.counts: dict[str, int] = {"found": 0, "missing": 0, "processed": 0}

    def tally(self, found: int, missing: int, processed: int = 0) -> None:
        self.counts = {"found": found, "missing": missing, "processed": processed}
        self.update(self._text())

    def reset(self) -> None:
        self.tally(0, 0, 0)

    def imported(self, summary: RunSummary) -> None:
        """Show what Anki did: added, updated, skipped and failed."""
        self.counts = {
            "added": summary.added,
            "updated": summary.updated,
            "skipped": summary.skipped,
            "failed": summary.failed,
        }
        parts = [
            f"{value} {name}"
            for name, value in self.counts.items()
            if value or name == "added"
        ]
        self.update(", ".join(parts))

    def _text(self) -> str:
        found = self.counts["found"]
        parts = [f"found {found}"]
        if self.counts["missing"]:
            parts.append(f"missing {self.counts['missing']}")
        if self.counts["processed"]:
            parts.append(f"processed {self.counts['processed']}")
        return "  ".join(parts)


class LogPanel(RichLog):
    """The run's own log, so nothing has to be printed under the app."""

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id, wrap=True, highlight=False, markup=False)
        self.entries: list[str] = []

    def add_line(self, line: str) -> None:
        self.entries.append(line)
        self.write(line)

    def clear_entries(self) -> None:
        self.entries.clear()
        self.clear()

    def hide_panel(self) -> None:
        self.display = False

    def show_panel(self) -> None:
        self.display = True
