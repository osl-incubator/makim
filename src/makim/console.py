"""Functions about console."""
import os


def get_terminal_size(default_size=(80, 24)):
    """Return the height (number of lines) of the terminal using os module."""
    try:
        size = os.get_terminal_size()
        return (size.columns, size.lines)
    except OSError:
        return default_size
