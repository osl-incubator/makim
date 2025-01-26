"""Cron command handling functions."""

from typing import Optional

import typer

from rich.console import Console
from rich.table import Table

from makim.cli.auto_generator import create_dynamic_command_cron
from makim.core import Makim


def _create_cron_table() -> Table:
    """Create a table for displaying scheduled tasks."""
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('Name', style='cyan')
    table.add_column('Task', style='blue')
    table.add_column('Schedule', style='yellow')
    table.add_column('Status', style='green')
    table.add_column('Next Run', style='magenta')
    return table


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
    name: Optional[str],
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
    name: Optional[str],
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
