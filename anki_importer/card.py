"""A flashcard, built from one Obsidian note and ready to be submitted to Anki."""

from dataclasses import dataclass, field


@dataclass
class Card:
    """One note, rendered as an Anki card.

    `front` is the prompt, `back` the HTML answer, `tags` the Anki tags.
    `staged_content` is the note body as it stood after frontmatter was removed
    but before markdown was rendered, which is what the link and image passes
    rewrite. `should_skip` marks a card the user does not want imported.
    """

    front: str = ""
    back: str = ""
    frontmatter: dict[str, object] | None = None
    staged_content: str = ""
    should_skip: bool = False
    tags: set[str] = field(default_factory=set)

    def __repr__(self) -> str:
        return f"Card(front={self.front!r}, back={self.back[:20]!r}..., tags={self.tags})"