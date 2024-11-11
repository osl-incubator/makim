"""CLI functions to define the arguments and call Makim."""

from __future__ import annotations

import os
import sys

from typing import Any, cast

import typer

from rich.console import Console
from rich.table import Table

from makim import __version__
from makim.cli.auto_generator import (
    create_dynamic_command,
    create_dynamic_command_cron,
    suggest_command,
)
from makim.cli.config import CLI_ROOT_FLAGS_VALUES_COUNT, extract_root_config
from makim.core import Makim

app = typer.Typer(
    help=(
        'Makim is a tool that helps you to organize '
        'and simplify your helper commands.'
    ),
    epilog=(
        'If you have any problem, open an issue at: '
        'https://github.com/osl-incubator/makim'
    ),
)

makim: Makim = Makim()


@app.callback(invoke_without_command=True)
def main(
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


def _create_cron_table() -> Table:
    """Create a table for displaying scheduled tasks."""
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('Name', style='cyan')
    table.add_column('Task', style='blue')
    table.add_column('Schedule', style='yellow')
    table.add_column('Status', style='green')
    table.add_column('Next Run', style='magenta')
    return table


def _handle_cron_list(makim_instance: Makim) -> None:
    """Handle the cron list command."""
    scheduled_tasks = makim_instance.global_data.get('scheduler', {})

    if not scheduled_tasks:
        typer.echo('No scheduled tasks configured in .makim.yaml')
        return

    console = Console()
    table = _create_cron_table()

    active_jobs = {
        job['name']: job
        for job in (
            makim_instance.scheduler.list_jobs()
            if makim_instance.scheduler
            else []
        )
    }

    for name, config in scheduled_tasks.items():
        active_job = active_jobs.get(name)
        status = 'Active' if active_job else 'Inactive'
        next_run = (
            active_job['next_run_time'] if active_job else 'Not scheduled'
        )

        table.add_row(
            name,
            config.get('task', 'N/A'),
            config.get('schedule', 'N/A'),
            status,
            next_run or 'Not scheduled',
        )

    console.print(table)


def _handle_cron_start(
    makim_instance: Makim,
    name: str | None,
    all_jobs: bool,
) -> None:
    """Handle the cron start command."""
    if not makim_instance.scheduler:
        typer.echo('No scheduler configured.')
        return

    scheduled_tasks = makim_instance.global_data.get('scheduler', {})

    if all_jobs:
        success_count = 0
        error_count = 0
        for schedule_name, schedule_config in scheduled_tasks.items():
            try:
                makim_instance.scheduler.add_job(
                    name=schedule_name,
                    schedule=schedule_config['schedule'],
                    task=schedule_config['task'],
                    args=schedule_config.get('args', {}),
                )
                success_count += 1
                typer.echo(f"Successfully started schedule '{schedule_name}'")
            except Exception as e:
                error_count += 1
                typer.echo(
                    f"Failed to start schedule '{schedule_name}': {e}",
                    err=True,
                )

        typer.echo(
            f'\nSummary: {success_count} jobs started successfully, '
            f'{error_count} failed'
        )
        return

    if not name:
        typer.echo("Please provide a scheduler name or use '--all' flag")
        raise typer.Exit(1)

    try:
        schedule_config = scheduled_tasks.get(name)
        if not schedule_config:
            typer.echo(f"No configuration found for schedule '{name}'")
            return

        makim_instance.scheduler.add_job(
            name=name,
            schedule=schedule_config['schedule'],
            task=schedule_config['task'],
            args=schedule_config.get('args', {}),
        )
        typer.echo(f"Successfully started schedule '{name}'")
    except Exception as e:
        typer.echo(f"Failed to start schedule '{name}': {e}", err=True)


def _handle_cron_stop(
    makim_instance: Makim,
    name: str | None,
    all_jobs: bool,
) -> None:
    """Handle the cron stop command."""
    if not makim_instance.scheduler:
        typer.echo('No scheduler configured.')
        return

    if all_jobs:
        active_jobs = makim_instance.scheduler.list_jobs()
        success_count = 0
        error_count = 0

        for job in active_jobs:
            try:
                makim_instance.scheduler.remove_job(job['name'])
                success_count += 1
                typer.echo(f"Successfully stopped schedule '{job['name']}'")
            except Exception as e:
                error_count += 1
                typer.echo(
                    f"Failed to stop schedule '{job['name']}': {e}",
                    err=True,
                )

        typer.echo(
            f'\nSummary: {success_count} jobs stopped successfully, '
            f'{error_count} failed'
        )
        return

    if not name:
        typer.echo("Please provide a scheduler name or use '--all' flag")
        raise typer.Exit(1)

    try:
        makim_instance.scheduler.remove_job(name)
        typer.echo(f"Successfully stopped schedule '{name}'")
    except Exception as e:
        typer.echo(f"Failed to stop schedule '{name}': {e}", err=True)


def _handle_cron_commands(makim_instance: Makim) -> typer.Typer:
    """Create and handle cron-related commands.

    Returns
    -------
        typer.Typer: The cron command group with all subcommands.
    """
    typer_cron = typer.Typer(
        help='Tasks Scheduler',
        invoke_without_command=True,
    )

    if 'scheduler' in makim_instance.global_data:
        for schedule_name, schedule_params in makim_instance.global_data.get(
            'scheduler', {}
        ).items():
            create_dynamic_command_cron(
                makim_instance,
                typer_cron,
                schedule_name,
                schedule_params or {},
            )

        @typer_cron.command(help='List all scheduled tasks')
        def list() -> None:
            """List tasks defined in .makim.yaml and their current status."""
            _handle_cron_list(makim_instance)

        @typer_cron.command(help='Start a scheduler by its name')
        def start(
            name: str = typer.Argument(
                None,
                help="""Name of the scheduler to start.
                Use '--all' for all schedulers""",
            ),
            all: bool = typer.Option(
                False,
                '--all',
                help='Start all available schedulers',
                is_flag=True,
            ),
        ) -> None:
            """Start (enable) a scheduled task."""
            _handle_cron_start(makim_instance, name, all)

        @typer_cron.command(help='Stop a scheduler by its name')
        def stop(
            name: str = typer.Argument(
                None,
                help="""Name of the scheduler to stop.
                Use '--all' for all schedulers""",
            ),
            all: bool = typer.Option(
                False,
                '--all',
                help='Stop all running schedulers',
                is_flag=True,
            ),
        ) -> None:
            """Stop (disable) scheduled task(s)."""
            _handle_cron_stop(makim_instance, name, all)

    return typer_cron


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
    )

    tasks: dict[str, Any] = {}
    for group_name, group_data in makim.global_data.get('groups', {}).items():
        for task_name, task_data in group_data.get('tasks', {}).items():
            tasks[f'{group_name}.{task_name}'] = task_data

    # Add dynamically cron commands to Typer app
    if 'scheduler' in makim.global_data:
        typer_cron = typer.Typer(
            help='Tasks Scheduler',
            invoke_without_command=True,
        )

        for schedule_name, schedule_params in makim.global_data.get(
            'scheduler', {}
        ).items():
            create_dynamic_command_cron(
                makim, typer_cron, schedule_name, schedule_params or {}
            )

        # Add cron command
        app.add_typer(typer_cron, name='cron', rich_help_panel='Extensions')

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
