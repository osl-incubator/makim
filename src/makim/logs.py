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
    SSH_AUTHENTICATION_FAILED = 15
    SSH_CONNECTION_ERROR = 16
    SSH_EXECUTION_ERROR = 17
    REMOTE_HOST_NOT_FOUND = 18
    SCHEDULER_JOB_ERROR = 19
    SCHEDULER_JOB_NOT_FOUND = 20
    SCHEDULER_INVALID_SCHEDULE = 21
    MAKIM_SCHEMA_FILE_NOT_FOUND = 22
    MAKIM_NO_BACKEND_FOUND = 23


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

    console = Console()

    @staticmethod
    def log_failure(task_name: str, error_message: str):
        """Logs a task failure with detailed error information."""
        MakimLogs.console.print(f"[bold red]Task '{task_name}' failed:[/bold red] {error_message}")

    @staticmethod
    def generate_error_report(failed_tasks):
        """Generates a structured error report for pipeline failures."""
        if not failed_tasks:
            return

        MakimLogs.console.print("\n[bold red]Pipeline Execution Failed[/bold red]")
        MakimLogs.console.print("[bold]Error Summary:[/bold]")

        for task, error in failed_tasks.items():
            MakimLogs.console.print(f"  ❌ [red]Task: {task}[/red]")
            MakimLogs.console.print(f"     [yellow]Error: {error}[/yellow]")

    live_log = None

    @staticmethod
    def start_live_logging():
        """Initialize live logging display."""
        if MakimLogs.live_log is None:
            table = Table(title="Pipeline Execution Status")
            table.add_column("Task", justify="left")
            table.add_column("Status", justify="left")
            MakimLogs.live_log = Live(table, refresh_per_second=2)
            MakimLogs.live_log.start()

    @staticmethod
    def update_live_log(task_name, status):
        """Update the live logging display with task execution status."""
        if MakimLogs.live_log:
            table = MakimLogs.live_log.renderable
            table.add_row(task_name, status)
            MakimLogs.live_log.update(table)

    @staticmethod
    def stop_live_logging():
        """Stop live logging display."""
        if MakimLogs.live_log:
            MakimLogs.live_log.stop()
            MakimLogs.live_log = None