"""Functions about console."""

from __future__ import annotations

import os


def get_terminal_size(
    default_size: tuple[int, int] = (80, 24),
) -> tuple[int, int]:
    """Return the height (number of lines) of the terminal using os module."""
    try:
        size = os.get_terminal_size()
        return (size.columns, size.lines)
    except OSError:
        return default_size
