"""Functions about console."""

import os

from typing import Tuple


def get_terminal_size(
    default_size: Tuple[int, int] = (80, 24),
) -> Tuple[int, int]:
    """Return the height (number of lines) of the terminal using os module."""
    try:
        size = os.get_terminal_size()
        return (size.columns, size.lines)
    except OSError:
        return default_size
