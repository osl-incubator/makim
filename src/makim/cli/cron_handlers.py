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
        def list(
            all_jobs: bool = typer.Option(
                False, '--all', help='List all cron jobs'
            ),
            pipeline_name: Optional[str] = typer.Argument(
                None, help='Filter cron jobs by pipeline name'
            ),
        ) -> None:
            """List tasks with filtering for all jobs or specific pipelines."""
            _handle_cron_list(
                makim_instance, pipeline_name=pipeline_name, all_jobs=all_jobs
            )

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


def _handle_cron_list(
    makim_instance: Makim,
    pipeline_name: Optional[str] = None,
    all_jobs: bool = False,
) -> None:
    """Handle the cron list command, supporting all, pipeline-specific, or standard cron jobs."""
    scheduled_tasks = makim_instance.global_data.get('scheduler', {})
    pipeline_tasks = makim_instance.global_data.get('pipelines', {})

    if not scheduled_tasks and not pipeline_tasks:
        typer.echo(
            '❌ No scheduled cron or pipeline jobs configured in .makim.yaml'
        )
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

    def add_task_to_table(name, config, is_pipeline=False):
        active_job = active_jobs.get(name)
        status = '🟢 Active' if active_job else '🔴 Inactive'
        next_run = (
            str(active_job['next_run_time']) if active_job else 'Not scheduled'
        )

        table.add_row(
            name,
            config.get('task', 'Pipeline' if is_pipeline else 'N/A'),
            config.get('schedule', 'N/A'),
            status,
            next_run or 'Not scheduled',
        )

    if all_jobs:
        for name, config in scheduled_tasks.items():
            add_task_to_table(name, config)
        for name, config in pipeline_tasks.items():
            add_task_to_table(name, config, is_pipeline=True)

    elif pipeline_name:
        filtered_tasks = {
            name: config
            for name, config in scheduled_tasks.items()
            if config.get('task', '').startswith(f'{pipeline_name}.')
        }
        if not filtered_tasks:
            typer.echo(
                f"❌ No cron jobs found for pipeline '{pipeline_name}'."
            )
            return
        for name, config in filtered_tasks.items():
            add_task_to_table(name, config)

    else:
        for name, config in scheduled_tasks.items():
            add_task_to_table(name, config)

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
        job = makim_instance.scheduler.get_job(name)
        if not job:
            typer.echo(f"❌ No running job found with the name '{name}'.")
            return

        makim_instance.scheduler.remove_job(name)
        typer.echo(f"Successfully stopped schedule '{name}'")
    except Exception as e:
        typer.echo(f"Failed to stop schedule '{name}': {e}", err=True)
