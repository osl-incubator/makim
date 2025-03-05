"""CLI functions to define the arguments and call Makim."""

from __future__ import annotations

import os
import sys

from typing import Any, cast

import typer

from makim import __version__
from makim.cli.auto_generator import (
    create_dynamic_command,
    suggest_command,
)
from makim.cli.config import CLI_ROOT_FLAGS_VALUES_COUNT, extract_root_config
from makim.cli.cron_handlers import (
    _handle_cron_commands,
)
from makim.core import Makim

app = typer.Typer(
    help=(
        'Makim is an automation tool focused on improving task management '
        'using YAML format.'
    ),
    epilog=(
        'If you have any problem, open an issue at: '
        'https://github.com/osl-incubator/makim'
    ),
)

makim: Makim = Makim()


@app.callback(invoke_without_command=True)
def main(  # noqa: PLR0913
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        '--version',
        '-v',
        is_flag=True,
        help='Show the version and exit',
    ),
    file: str = typer.Option(
        '.makim.yaml',
        '--file',
        help='Makim config file',
    ),
    dry_run: bool = typer.Option(
        None,
        '--dry-run',
        is_flag=True,
        help='Execute the command in dry mode',
    ),
    verbose: bool = typer.Option(
        None,
        '--verbose',
        is_flag=True,
        help='Execute the command in verbose mode',
    ),
    skip_hooks: bool = typer.Option(
        None,
        '--skip-hooks',
        is_flag=True,
        help='Skip hooks while executing the command',
    ),
) -> None:
    """Process top-level flags; otherwise, show the help menu."""
    typer.echo(f'Makim file: {file}')

    if version:
        typer.echo(f'Version: {__version__}')
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


def _get_command_from_cli() -> str:
    """
    Get the group and task from CLI.

    This function is based on `CLI_ROOT_FLAGS_VALUES_COUNT`.
    """
    params = sys.argv[1:]
    command = ''

    try:
        idx = 0
        while idx < len(params):
            arg = params[idx]
            if arg not in CLI_ROOT_FLAGS_VALUES_COUNT:
                command = f'flag `{arg}`' if arg.startswith('--') else arg
                break

            idx += 1 + CLI_ROOT_FLAGS_VALUES_COUNT[arg]
    except Exception as e:
        print(e)

    return command


def run_app() -> None:
    """Run the Typer app."""
    root_config = extract_root_config()
    config_file_path = cast(str, root_config.get('file', '.makim.yaml'))

    cli_completion_words = [
        w for w in os.getenv('COMP_WORDS', '').split('\n') if w
    ]

    if not makim._check_makim_file(config_file_path) and cli_completion_words:
        root_config = extract_root_config(cli_completion_words)
        config_file_path = cast(str, root_config.get('file', '.makim.yaml'))
        if not makim._check_makim_file(config_file_path):
            return

    makim.load(
        file=config_file_path,
        dry_run=cast(bool, root_config.get('dry_run', False)),
        verbose=cast(bool, root_config.get('verbose', False)),
        skip_hooks=cast(bool, root_config.get('skip_hooks', False)),
    )

    tasks: dict[str, Any] = {}
    for group_name, group_data in makim.global_data.get('groups', {}).items():
        for task_name, task_data in group_data.get('tasks', {}).items():
            tasks[f'{group_name}.{task_name}'] = task_data

    # Add dynamically commands to Typer app
    # Add cron commands if scheduler is configured
    typer_cron = _handle_cron_commands(makim)
    app.add_typer(typer_cron, name='cron', rich_help_panel='Extensions')

    # Add dynamic commands
    for name, args in tasks.items():
        create_dynamic_command(makim, app, name, args)

    try:
        app()
    except SystemExit as e:
        # Code 2 means command not found
        error_code = 2
        if e.code != error_code:
            raise e

        command_used = _get_command_from_cli()
        available_cmds = [
            cmd.name for cmd in app.registered_commands if cmd.name is not None
        ]
        suggestion = suggest_command(command_used, available_cmds)

        typer.secho(
            f"Command {command_used} not found. Did you mean '{suggestion}'?",
            fg='red',
        )
        raise e


if __name__ == '__main__':
    run_app()
