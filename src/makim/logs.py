"""Classes and function for handling logs."""

import os

from enum import Enum

from rich.console import Console


class MakimError(Enum):
    """Type error class."""

    SH_ERROR_RETURN_CODE = 1
    SH_KEYBOARD_INTERRUPT = 2
    MAKIM_CONFIG_FILE_NOT_FOUND = 3
    MAKIM_NO_TARGET_GROUPS_FOUND = 4
    MAKIM_TARGET_NOT_FOUND = 5
    MAKIM_GROUP_NOT_FOUND = 6
    MAKIM_VARS_ATTRIBUTE_INVALID = 7
    MAKIM_ARGUMENT_REQUIRED = 8
    MAKIM_ENV_FILE_NOT_FOUND = 9
    MAKIM_CONFIG_FILE_INVALID = 10
    CONFIG_VALIDATION_ERROR = 11
    YAML_PARSING_ERROR = 12
    JSON_SCHEMA_DECODING_ERROR = 13
    CONFIG_VALIDATION_UNEXPECTED_ERROR = 14


class MakimLogs:
    """MakimLogs is responsible for handling system messages."""

    @staticmethod
    def raise_error(
        message: str, message_type: MakimError, command_error: int = 1
    ) -> None:
        """Print error message and exit with given error code."""
        console = Console(stderr=True, style='bold red')
        console.print(f'Makim Error #{message_type.value}: {message}')
        raise os._exit(command_error)

    @staticmethod
    def print_info(message: str) -> None:
        """Print info message."""
        console = Console(style='blue')
        console.print(message)

    @staticmethod
    def print_warning(message: str) -> None:
        """Print warning message."""
        console = Console(style='yellow')
        console.print(message)
