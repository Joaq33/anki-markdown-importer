"""The app's visual identity: one palette, both themes from the same source.

Everything in the UI references theme variables (`$primary`, `$surface`,
`$text-muted`, …), never literal colors, so this file is the only place the
look lives. Textual derives the light variant from the same roles.
"""

from textual.theme import Theme

ANKI_THEME = Theme(
    name="anki",
    primary="#5b9cf5",
    secondary="#2e4a68",
    accent="#e0a63c",
    foreground="#dde3ea",
    background="#0e1116",
    surface="#151a21",
    panel="#1a2029",
    success="#4caf7d",
    warning="#d9a13b",
    error="#e5534b",
    dark=True,
)

THEME_NAME = ANKI_THEME.name