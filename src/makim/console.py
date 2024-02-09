"""Functions about console."""
import os


def get_terminal_size():
    """Return the height (number of lines) of the terminal using os module."""
    size = os.get_terminal_size()
    try:
        height = size.lines
    except OSError:
        # Default to 24 lines if the terminal size cannot be determined.
        height = 24

    try:
        width = size.columns
    except OSError:
        # Default to 24 lines if the terminal size cannot be determined.
        height = 80
    return width, height
