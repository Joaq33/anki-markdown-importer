"""Finding which notes belong to a run.

Starting from a handful of root notes, the notes an import should cover are the
root notes plus everything they link to, transitively. Links are followed one
depth at a time, and each note is read once: the content a discovery step yields
is the same text the card builder needs, so a vault is never read twice.
"""

import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol

from .card_builder import CardBuilder


@dataclass(frozen=True)
class NoteFound:
    """A note that exists, along with its text."""

    name: str
    content: str


@dataclass(frozen=True)
class NoteMissing:
    """Something linked to a note that is not in the vault."""

    name: str


NoteEvent = NoteFound | NoteMissing


class NoteSource(Protocol):
    """Where notes come from. The vault's filesystem, in production."""

    def read(self, name: str) -> str:
        """The text of the note called `name` (its stem, extension optional)."""

    def exists(self, name: str) -> bool: ...


class FolderNoteSource:
    """Reads notes from one flat folder, matching names case-insensitively."""

    def __init__(self, folder_path: str | os.PathLike[str]) -> None:
        self.folder_path = os.fspath(folder_path)
        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"Folder '{self.folder_path}' does not exist.")

    def read(self, name: str) -> str:
        try:
            entries = os.listdir(self.folder_path)
        except OSError as error:
            raise IOError(
                f"Error accessing directory or file: {error}"
            ) from error

        wanted = name.lower()
        for entry in entries:
            stem, extension = os.path.splitext(entry)
            if extension in (".md", ".markdown") and stem.lower() == wanted:
                path = os.path.join(self.folder_path, entry)
                if not os.path.isfile(path):
                    raise IOError(f"File '{entry}' is not a regular file.")
                with open(path, encoding="utf-8") as handle:
                    return handle.read()

        raise FileNotFoundError(
            f"Markdown file '{name}' not found in directory '{self.folder_path}'."
        )

    def exists(self, name: str) -> bool:
        try:
            self.read(name)
        except (FileNotFoundError, IOError):
            return False
        return True


class NoteDiscovery:
    """Walks the wiki-link graph breadth first from a set of root notes."""

    def __init__(self, source: NoteSource) -> None:
        self._source = source
        self._tracked: set[str] = set()

    @property
    def tracked(self) -> set[str]:
        """Every note name seen so far, in no particular order."""
        return set(self._tracked)

    def discover(self, roots: Iterable[str]) -> Iterator[NoteEvent]:
        """Yield every note reachable from `roots`, one link depth at a time.

        A link pointing at a note that is not in the vault is yielded as
        `NoteMissing` rather than raising, so one broken link does not end the run.
        """
        frontier = [name for name in roots if name]
        while frontier:
            following: list[str] = []
            for name in frontier:
                if name in self._tracked:
                    continue
                self._tracked.add(name)
                try:
                    content = self._source.read(name)
                except (FileNotFoundError, IOError):
                    yield NoteMissing(name)
                    continue
                yield NoteFound(name, content)
                for target in CardBuilder.wiki_link_targets(content):
                    if target not in self._tracked and target not in following:
                        following.append(target)
            frontier = following