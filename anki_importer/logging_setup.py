"""Where log output goes.

Nothing configures logging at import time: a library that installs global log
sinks as a side effect corrupts whatever is rendering the terminal. The app calls
`configure_file_logging` when it starts, and the TUI adds its own sink so lines
appear in its log panel instead of scrolling past underneath the UI.
"""

import os
from collections.abc import Callable
from typing import Any

from loguru import logger as log

DEFAULT_LOG_PATH = "./logs/anki_importer.log"
MAX_LOG_BYTES = "2.55 MB"  # keeps PyCharm's log viewer happy
RETENTION = "10 days"

LogSink = Callable[[str], None]


def configure_file_logging(path: str = DEFAULT_LOG_PATH) -> None:
    """Send every line to a rotating log file, and nowhere else."""
    log.remove()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    log.add(
        sink=path,
        level="DEBUG",
        rotation=MAX_LOG_BYTES,
        retention=RETENTION,
    )


def add_sink(sink: LogSink, level: str = "DEBUG", **options: Any) -> int:
    """Add a sink of your own, e.g. one that feeds the TUI's log panel."""
    return log.add(sink=sink, level=level, format="{message}", **options)


def remove_sink(handler_id: int) -> None:
    log.remove(handler_id)


def take_over_terminal(sink: LogSink, level: str = "INFO") -> int:
    """Stop logging to the terminal and hand every line to `sink` instead.

    A full-screen app owns the terminal: loguru's default handler would print
    straight through the UI, so it is removed before the app takes over.
    """
    log.remove()
    return add_sink(sink, level=level)
