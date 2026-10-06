"""What an Anki card will actually say, in plain text.

A terminal cannot render Anki's HTML, so the detail screen shows the back with
the markup taken off: one line per thought, list items bulleted, entities
unescaped, everything else dropped.
"""

import html as html_module
import re

BLOCK_ENDS = re.compile(
    r"</(?:p|div|h[1-6]|ul|ol|blockquote|tr|table|pre)>|<br\s*/?>|<hr\s*/?>",
    re.IGNORECASE,
)
LIST_ITEM = re.compile(r"<li(?:\s[^>]*)?>|</li>", re.IGNORECASE)
ANY_TAG = re.compile(r"<[^>]+>")
BULLET = "\u2022 "


def plain_preview(back_html: str) -> str:
    """The text a reader takes away from a card's back."""
    bulleted = LIST_ITEM.sub(lambda match: "\n" + BULLET if match.group(0).startswith("<li") else "", back_html)
    broken = BLOCK_ENDS.sub("\n", bulleted)
    stripped = ANY_TAG.sub("", broken)
    unescaped = html_module.unescape(stripped)
    return "\n".join(line.strip() for line in unescaped.splitlines() if line.strip())