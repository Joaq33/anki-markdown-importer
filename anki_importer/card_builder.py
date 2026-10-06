"""Turning one Obsidian note into an Anki card.

Pure: the only inputs are a note's name, its text and the run settings, and the
only output is a `Card`. Nothing here reads files, talks to Anki or writes logs,
so it can be exercised with no Anki running and no terminal.
"""

import os
import re
from typing import Any

import frontmatter
from markdown_it import MarkdownIt

from .card import Card

WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")
IMAGE_EMBED = re.compile(
    r"!\[\[([^|\]]+\.(?:png|jpg|jpeg|gif|bmp|svg|webp|tiff|tif|ico))(?:\|[^\]]*)?\]\]"
)
HASHTAG = re.compile(r"#(\w+)")
DATAVIEW_FORMULA = r'`?="\$"\s*\+\s*this\.formula\s*\+\s*"\$"`?'
BODY_SEPARATOR = "\n---\n"

CALLOUT = re.compile(
    r"^(> \[!(?P<type>[a-zA-Z]+)\](?P<title>.*?)$(?:\n>.*)*)", re.MULTILINE
)

CALLOUT_COLOURS: dict[str, tuple[str, str]] = {
    "info": ("#3b82f6", "rgba(59, 130, 246, 0.08)"),
    "note": ("#3b82f6", "rgba(59, 130, 246, 0.08)"),
    "tip": ("#10b981", "rgba(16, 185, 129, 0.08)"),
    "success": ("#10b981", "rgba(16, 185, 129, 0.08)"),
    "warning": ("#f59e0b", "rgba(245, 158, 11, 0.08)"),
    "danger": ("#ef4444", "rgba(239, 68, 68, 0.08)"),
    "error": ("#ef4444", "rgba(239, 68, 68, 0.08)"),
    "example": ("#8e8e93", "rgba(142, 142, 147, 0.08)"),
}
DEFAULT_CALLOUT_COLOURS = ("#6b7280", "rgba(107, 114, 128, 0.08)")
# Callouts whose custom title replaces the type name still show the type.
TYPED_CALLOUTS = frozenset({"example", "tip", "warning", "error"})


class CardBuilder:
    """Builds cards from note text. Holds no state between notes."""

    not_included_tag = "not_included"

    def __init__(self, not_included_tag: str | None = None) -> None:
        if not_included_tag is not None:
            self.not_included_tag = not_included_tag

    def build(
        self,
        name: str,
        content: str,
        *,
        card_prefix: str = "",
        generate_links: bool = True,
    ) -> Card:
        """Build the card for one note.

        `name` is the note's file name, with or without its extension.
        """
        card = Card()
        parsed, body = frontmatter.parse(content)
        card.frontmatter = parsed if isinstance(parsed, dict) else {}
        card.staged_content = str(body)

        card.tags.update(self._tags_from_frontmatter(card.frontmatter))
        card.tags.update(HASHTAG.findall(card.staged_content))

        if self.not_included_tag in card.tags:
            card.front = card_prefix + name
            card.back = f"This note is skipped due to the '{self.not_included_tag}' tag."
            card.should_skip = True
            return card

        card.front = card_prefix + os.path.splitext(name)[0]
        body = card.staged_content
        body = self._replace_images(body)
        body = self._replace_wiki_links(body, generate_links)
        body = self.replace_formula_property(body, card.frontmatter)
        body = self.format_callouts(body)
        card.staged_content = body
        card.back = self.markdown_to_html(body)
        return card

    @staticmethod
    def markdown_to_html(md_content: str) -> str:
        """Render markdown to HTML, guarding LaTeX so it stays MathJax for Anki."""
        math_blocks: list[str] = []

        def stash(match: re.Match[str]) -> str:
            math_blocks.append(match.group(1))
            return f"MATH_BLOCK_{len(math_blocks) - 1}_END"

        def stash_inline(match: re.Match[str]) -> str:
            math_blocks.append(match.group(1))
            return f"MATH_INLINE_{len(math_blocks) - 1}_END"

        guarded = re.sub(r"\$\$(.*?)\$\$", stash, md_content, flags=re.DOTALL)
        guarded = re.sub(r"\$(.*?)\$", stash_inline, guarded, flags=re.DOTALL)
        html: str = MarkdownIt().render(guarded)
        for index, formula in enumerate(math_blocks):
            html = html.replace(f"MATH_BLOCK_{index}_END", f"\\[{formula}\\]")
            html = html.replace(f"MATH_INLINE_{index}_END", f"\\({formula}\\)")
        return html

    @staticmethod
    def wiki_link_targets(content: str) -> list[str]:
        """The notes `content` links to, in the order they appear."""
        targets: list[str] = []
        for match in WIKI_LINK.finditer(content):
            target = match.group(1).split("|")[0].strip()
            if target and target not in targets:
                targets.append(target)
        return targets

    @staticmethod
    def _tags_from_frontmatter(parsed: Any) -> list[str]:
        if not isinstance(parsed, dict):
            return []
        tags = parsed.get("tags")
        if tags is None:
            return []
        if isinstance(tags, str):
            return [tags]
        return [str(tag) for tag in tags]

    @staticmethod
    def _replace_images(content: str) -> str:
        return IMAGE_EMBED.sub("*__[image_placeholder]__*", content)

    @staticmethod
    def _replace_wiki_links(content: str, generate_links: bool) -> str:
        def rewrite(match: re.Match[str]) -> str:
            parts = match.group(1).split("|")
            target = parts[0].strip()
            alias = parts[1].strip() if len(parts) > 1 else target
            if generate_links:
                # A placeholder the link-resolution pass swaps for a real note id.
                return f"[{alias}|nidPENDING:{target}]"
            return alias

        return WIKI_LINK.sub(rewrite, content).split(BODY_SEPARATOR, 1)[0]

    @staticmethod
    def replace_formula_property(content: str, parsed: Any) -> str:
        formula = parsed.get("formula") if isinstance(parsed, dict) else None
        if formula is None:
            return content
        return re.sub(DATAVIEW_FORMULA, lambda _: f"${formula}$", content)

    @classmethod
    def format_callouts(cls, content: str) -> str:
        def render(match: re.Match[str]) -> str:
            callout_type = match.group("type").lower()
            raw_title = match.group("title").strip()
            has_custom_title = bool(raw_title)
            title = raw_title if has_custom_title else callout_type.capitalize()
            colour, background = CALLOUT_COLOURS.get(callout_type, DEFAULT_CALLOUT_COLOURS)

            if has_custom_title and callout_type in TYPED_CALLOUTS:
                indicator = (
                    f'<div style="font-size: 0.75em; font-weight: normal; opacity: 0.6; '
                    f'text-transform: uppercase; margin-bottom: 2px; color: {colour};">'
                    f"[{callout_type}]</div>"
                )
                title_block = (
                    f'{indicator}<div style="font-weight: bold; font-size: 1.05em; '
                    f'color: inherit;">{title}</div>'
                )
            elif has_custom_title:
                title_block = (
                    f'<div style="font-weight: bold; font-size: 1.05em; color: inherit;">'
                    f"{title}</div>"
                )
            else:
                title_block = (
                    f'<div style="font-weight: bold; font-size: 1.05em; color: {colour};">'
                    f"{title}</div>"
                )

            body = "\n".join(
                line[2:] if line.startswith("> ") else line[1:] if line.startswith(">") else line
                for line in match.group(1).split("\n")[1:]
            )
            opacity = "0.75" if callout_type == "example" else "0.9"
            return (
                f'<div class="callout callout-{callout_type}" style="text-align: left; '
                f"border-left: 4px solid {colour}; background-color: {background}; "
                'padding: 10px; margin: 10px 0; border-radius: 4px;">\n'
                f'<div class="callout-title" style="margin-bottom: 8px;">{title_block}</div>\n\n'
                f'<div class="callout-content" style="opacity: {opacity};">\n\n'
                f"{body}\n\n</div>\n\n</div>"
            )

        return CALLOUT.sub(render, content)