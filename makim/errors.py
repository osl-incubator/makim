"""Classes and function for handling logs."""
from enum import Enum


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
