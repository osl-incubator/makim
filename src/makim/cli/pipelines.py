"""Pipeline command handling functions."""

import time

from datetime import datetime
from typing import Any, Optional, cast

import typer

from rich import box
from rich.console import Console
from rich.highlighter import ReprHighlighter
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from makim.cli.auto_generator import create_dynamic_command_pipeline
from makim.core import Makim

# Constants
MAX_LOG_ROWS = 500
MAX_CONTENT_LENGTH = 200


def _create_pipeline_table() -> Table:
    """Create a table for displaying pipeline information."""
    table = Table(
        show_header=True, header_style='bold magenta', box=box.ROUNDED
    )
    table.add_column('Pipeline', style='cyan')
    table.add_column('Description', style='blue')
    table.add_column('Steps', style='yellow')
    table.add_column('Execution Mode', style='green')
    return table


def _create_schedule_table() -> Table:
    """Create a table for displaying scheduled pipelines."""
    table = Table(
        show_header=True, header_style='bold magenta', box=box.ROUNDED
    )
    table.add_column('ID', style='dim')
    table.add_column('Pipeline', style='cyan')
    table.add_column('Schedule', style='yellow')
    table.add_column('Last Run', style='blue')
    table.add_column('Next Run', style='green')
    table.add_column('Status', style='magenta')
    return table


def _create_history_table() -> Table:
    """Create a table for displaying pipeline execution history."""
    table = Table(
        show_header=True, header_style='bold magenta', box=box.ROUNDED
    )
    table.add_column('ID', style='dim')
    table.add_column('Pipeline', style='cyan')
    table.add_column('Status', style='yellow')
    table.add_column('Progress', style='blue')
    table.add_column('Start Time', style='green')
    table.add_column('End Time', style='magenta')
    table.add_column('Duration', style='bright_blue')
    return table


def _create_logs_table() -> Table:
    """Create a table for displaying pipeline logs."""
    table = Table(
        show_header=True, header_style='bold magenta', box=box.ROUNDED
    )
    table.add_column('Pipeline', style='cyan')
    table.add_column('Step', style='yellow')
    table.add_column('Type', style='blue')
    table.add_column('Timestamp', style='green')
    table.add_column('Content', style='white', no_wrap=False, max_width=80)
    return table


def _handle_pipeline_commands(makim_instance: Makim) -> typer.Typer:
    """Create and handle pipeline-related commands.

    Returns
    -------
        typer.Typer: The pipeline command group with all subcommands.
    """
    typer_pipeline = typer.Typer(
        help='Pipeline Management',
        invoke_without_command=True,
    )

    if hasattr(makim_instance, 'pipeline') and makim_instance.pipeline:
        # If pipelines are defined in the config, create dynamic commands
        # for each
        pipelines = makim_instance.pipeline.get_all_pipelines()
        for pipeline_name, pipeline_config in pipelines.items():
            create_dynamic_command_pipeline(
                makim_instance,
                typer_pipeline,
                pipeline_name,
                pipeline_config,
            )

        @typer_pipeline.command(help='Run a pipeline')
        def run(
            name: str = typer.Argument(
                ...,
                help='Name of the pipeline to run',
            ),
            parallel: bool = typer.Option(
                False,
                '--parallel',
                help='Run steps in parallel where possible',
                is_flag=True,
            ),
            sequential: bool = typer.Option(
                False,
                '--sequential',
                help='Run steps sequentially',
                is_flag=True,
            ),
            max_workers: Optional[int] = typer.Option(
                None,
                '--max-workers',
                help='Maximum number of parallel workers',
            ),
            verbose: bool = typer.Option(
                False,
                '--verbose',
                '-v',
                help='Show verbose output during pipeline execution',
                is_flag=True,
            ),
            dry_run: bool = typer.Option(
                False,
                '--dry-run',
                help='Show steps without executing them',
                is_flag=True,
            ),
            debug: bool = typer.Option(
                False,
                '--debug',
                help='Show detailed debug information',
                is_flag=True,
            ),
        ) -> None:
            """Run a pipeline by its name."""
            # Determine execution mode
            execution_mode: Optional[str] = None
            if parallel and sequential:
                console = Console()
                console.print(
                    '[bold red]Error:[/] Cannot specify both --parallel and'
                    ' --sequential'
                )
                raise typer.Exit(code=1)
            elif parallel:
                execution_mode = 'parallel'
            elif sequential:
                execution_mode = 'sequential'

            _handle_pipeline_run(
                makim_instance,
                name,
                execution_mode=execution_mode,
                max_workers=max_workers,
                verbose=verbose,
                dry_run=dry_run,
                debug=debug,
            )

        @typer_pipeline.command(help='Show pipeline structure')
        def show(
            name: Optional[str] = typer.Argument(
                None,
                help='Name of the pipeline to show. If not provided, shows '
                'all pipelines.',
            ),
            run_id: Optional[str] = typer.Option(
                None,
                '--run-id',
                help='Run ID to show status information for',
            ),
            status: bool = typer.Option(
                False,
                '--status',
                help='Include status information in visualization',
                is_flag=True,
            ),
        ) -> None:
            """Show the structure of a pipeline or list all pipelines."""
            _handle_pipeline_show(makim_instance, name, run_id, status)

        @typer_pipeline.command(help='List all defined pipelines')
        def list() -> None:
            """List all defined pipelines."""
            _handle_pipeline_list(makim_instance)

        @typer_pipeline.command(help='View pipeline execution logs')
        def logs(
            pipeline: Optional[str] = typer.Option(
                None,
                '--pipeline',
                help='Filter logs by pipeline name',
            ),
            run_id: Optional[str] = typer.Option(
                None,
                '--run-id',
                help='Filter logs by run ID',
            ),
            step: Optional[str] = typer.Option(
                None,
                '--step',
                help='Filter logs by step name',
            ),
            last: int = typer.Option(
                20,
                '--last',
                help='Number of most recent log entries to show',
            ),
            type: Optional[str] = typer.Option(
                None,
                '--type',
                help='Filter by log type (stdout, stderr)',
            ),
            follow: bool = typer.Option(
                False,
                '--follow',
                '-f',
                help='Follow log output for active pipelines',
                is_flag=True,
            ),
            clear: bool = typer.Option(
                False,
                '--clear',
                help='Clear all logs from the database',
                is_flag=True,
            ),
        ) -> None:
            """View pipeline execution logs."""
            _handle_pipeline_logs(
                makim_instance,
                pipeline_name=pipeline,
                run_id=run_id,
                step_name=step,
                limit=last,
                log_type=type,
                follow=follow,
                clear=clear,
            )

        @typer_pipeline.command(help='View pipeline execution history')
        def history(
            pipeline: Optional[str] = typer.Option(
                None,
                '--pipeline',
                help='Filter history by pipeline name',
            ),
            last: int = typer.Option(
                10,
                '--last',
                help='Number of most recent executions to show',
            ),
            status: Optional[str] = typer.Option(
                None,
                '--status',
                help='Filter by status (running, completed, failed, '
                'cancelled)',
            ),
            details: bool = typer.Option(
                False,
                '--details',
                '-d',
                help='Show detailed step information',
                is_flag=True,
            ),
        ) -> None:
            """View pipeline execution history."""
            _handle_pipeline_history(
                makim_instance,
                pipeline_name=pipeline,
                limit=last,
                status=status,
                details=details,
            )

        @typer_pipeline.command(
            help='Schedule a pipeline to run automatically'
        )
        def schedule(
            pipeline: str = typer.Argument(
                ...,
                help='Name of the pipeline to schedule',
            ),
            cron: Optional[str] = typer.Option(
                None,
                '--cron',
                help="Cron expression for scheduling (e.g., '0 9 * * *')",
            ),
            interval: Optional[int] = typer.Option(
                None,
                '--interval',
                help='Interval in seconds between executions',
            ),
        ) -> None:
            """Schedule a pipeline to run automatically."""
            _handle_pipeline_schedule(
                makim_instance, pipeline, cron=cron, interval=interval
            )

        @typer_pipeline.command(help='List all scheduled pipelines')
        def scheduled() -> None:
            """List all scheduled pipelines."""
            _handle_pipeline_scheduled(makim_instance)

        @typer_pipeline.command(help='Remove a scheduled pipeline')
        def unschedule(
            pipeline: str = typer.Argument(
                ...,
                help='Name of the pipeline to unschedule',
            ),
        ) -> None:
            """Remove a scheduled pipeline."""
            _handle_pipeline_unschedule(makim_instance, pipeline)

        @typer_pipeline.command(help='Retry a failed pipeline')
        def retry(
            pipeline: str = typer.Argument(
                ...,
                help='Name of the failed pipeline to retry',
            ),
            all: bool = typer.Option(
                False,
                '--all',
                help='Retry all steps, not just failed ones',
                is_flag=True,
            ),
        ) -> None:
            """Retry a failed pipeline."""
            _handle_pipeline_retry(makim_instance, pipeline, all)

        @typer_pipeline.command(help='Cancel a running pipeline')
        def cancel(
            pipeline: str = typer.Argument(
                ...,
                help='Name or ID of the running pipeline to cancel',
            ),
        ) -> None:
            """Cancel a running pipeline."""
            _handle_pipeline_cancel(makim_instance, pipeline)

    return typer_pipeline


def _handle_pipeline_run(
    makim_instance: Makim,
    name: str,
    execution_mode: Optional[str] = None,
    max_workers: Optional[int] = None,
    verbose: bool = False,
    dry_run: bool = False,
    debug: bool = False,
) -> None:
    """Handle the pipeline run command.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    name : str
        The name of the pipeline to run.
    execution_mode : Optional[str]
        Mode of execution: "sequential" or "parallel"
    max_workers : Optional[int]
        Maximum number of workers for parallel execution
    verbose : bool
        Whether to show verbose output.
    dry_run : bool
        If True, only shows steps without executing them
    debug : bool
        Enable detailed debug logging
    """
    try:
        pipeline = cast(Any, makim_instance.pipeline)
        success = pipeline.run_pipeline(
            name,
            execution_mode=execution_mode,
            max_workers=max_workers,
            verbose=verbose,
            dry_run=dry_run,
            debug=debug,
        )
        if not success and not dry_run:
            raise typer.Exit(code=1)
    except Exception as e:
        console = Console()
        console.print(f"[bold red]Error running pipeline '{name}':[/] {e!s}")
        raise typer.Exit(code=1)


def _handle_pipeline_show(
    makim_instance: Makim,
    name: Optional[str],
    run_id: Optional[str] = None,
    show_status: bool = False,
) -> None:
    """Handle the pipeline show command.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    name : Optional[str]
        The name of the pipeline to show. If None, shows all pipelines.
    run_id : Optional[str]
        Run ID to show status information for.
    show_status : bool
        Whether to include status information in visualization.
    """
    console = Console()
    pipeline = cast(Any, makim_instance.pipeline)

    if name:
        try:
            # Show rich tree visualization if available
            try:
                tree = pipeline.generate_rich_visualization(name, run_id)
                console.print(tree)
                return
            except (ImportError, AttributeError):
                # Fall back to ASCII art visualization
                pass

            # Show specific pipeline
            pipeline_viz = pipeline.visualize_pipeline(
                name, show_status=show_status, run_id=run_id
            )
            console.print(
                Panel(
                    pipeline_viz,
                    title=f'Pipeline: {name}',
                    border_style='blue',
                )
            )
        except ValueError as e:
            console.print(f'[bold red]Error:[/] {e!s}')
            raise typer.Exit(code=1)
    else:
        # List all pipelines with a brief overview
        _handle_pipeline_list(makim_instance)


def _handle_pipeline_list(makim_instance: Makim) -> None:
    """Handle listing all pipelines.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    """
    pipeline = cast(Any, makim_instance.pipeline)
    pipelines = pipeline.get_all_pipelines()

    if not pipelines:
        typer.echo('No pipelines defined in the configuration.')
        return

    console = Console()
    table = _create_pipeline_table()

    for name, config in pipelines.items():
        steps_count = len(config.get('steps', []))
        description = config.get('help', 'No description')
        execution_mode = config.get('default_execution_mode', 'sequential')

        table.add_row(name, description, str(steps_count), execution_mode)

    console.print(table)


def _handle_pipeline_logs(
    makim_instance: Makim,
    pipeline_name: Optional[str] = None,
    run_id: Optional[str] = None,
    step_name: Optional[str] = None,
    limit: int = 20,
    log_type: Optional[str] = None,
    follow: bool = False,
    clear: bool = False,
) -> None:
    """Handle viewing pipeline logs.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    pipeline_name : Optional[str]
        Filter logs by pipeline name.
    run_id : Optional[str]
        Filter logs by run ID.
    step_name : Optional[str]
        Filter logs by step name.
    limit : int
        Number of most recent log entries to show.
    log_type : Optional[str]
        Filter by log type (stdout, stderr).
    follow : bool
        Follow log output for active pipelines.
    clear : bool
        Clear all logs from the database.
    """
    console = Console()
    pipeline = cast(Any, makim_instance.pipeline)

    if clear:
        if pipeline.clear_logs():
            console.print('[green]Pipeline logs cleared successfully.[/]')
        else:
            console.print('[bold red]Failed to clear pipeline logs.[/]')
        return

    if follow:
        if not pipeline_name and not run_id:
            console.print(
                '[bold red]Error:[/] Either pipeline name or run ID is'
                ' required when using --follow'
            )
            raise typer.Exit(code=1)

        target = run_id or pipeline_name
        console.print(f'[bold]Following logs for:[/] [cyan]{target}[/]')
        console.print('[bold yellow]Press Ctrl+C to stop following logs[/]')

        # Set up rich live display
        layout = Layout()
        layout.split(
            Layout(name='header', size=3),
            Layout(name='main'),
        )

        # Create header
        header = Table.grid()
        header.add_column()
        header.add_row(f'[bold blue]Pipeline Logs: {target}[/]')
        header.add_row('[bold yellow]Press Ctrl+C to exit[/]')

        # Create logs table
        logs_table = Table(box=box.SIMPLE)
        logs_table.add_column('Time', style='dim')
        logs_table.add_column('Step', style='cyan')
        logs_table.add_column('Type', style='yellow', width=7)
        logs_table.add_column('Content', style='white', no_wrap=False)

        # Add to layout
        layout['header'].update(header)
        layout['main'].update(logs_table)

        # Initial logs
        logs = pipeline.get_pipeline_logs(
            run_id=run_id,
            pipeline_name=pipeline_name,
            step_name=step_name,
            limit=limit,
            log_type=log_type,
        )

        # Initialize table with existing logs
        for log in logs:
            timestamp = datetime.fromisoformat(log['timestamp']).strftime(
                '%H:%M:%S'
            )
            content = log['content'].strip()
            log_style = 'green' if log['log_type'] == 'stdout' else 'red'

            logs_table.add_row(
                timestamp,
                log['step_name'],
                f'[{log_style}]{log["log_type"]}[/]',
                content,
            )

        # Track last seen log ID for incremental updates
        last_id = max([log['id'] for log in logs]) if logs else 0

        # Set up the live display
        with Live(layout, refresh_per_second=4) as live:
            try:
                # Function to handle new log entries
                def update_logs() -> None:
                    nonlocal last_id
                    new_logs = pipeline.get_pipeline_logs(
                        run_id=run_id,
                        pipeline_name=pipeline_name,
                        step_name=step_name,
                        log_type=log_type,
                        since_id=last_id,
                    )

                    if new_logs:
                        last_id = max([log['id'] for log in new_logs])

                        for log in new_logs:
                            timestamp = datetime.fromisoformat(
                                log['timestamp']
                            ).strftime('%H:%M:%S')
                            content = log['content'].strip()
                            log_style = (
                                'green'
                                if log['log_type'] == 'stdout'
                                else 'red'
                            )

                            logs_table.add_row(
                                timestamp,
                                log['step_name'],
                                f'[{log_style}]{log["log_type"]}[/]',
                                content,
                            )

                            # Limit table size to avoid memory issues
                            if len(logs_table.rows) > MAX_LOG_ROWS:
                                logs_table.rows.pop(0)

                # Register callback for live updates if available
                try:
                    pipeline.follow_pipeline_logs(
                        run_id=run_id,
                        pipeline_name=pipeline_name,
                        callback=lambda log: logs_table.add_row(
                            datetime.fromisoformat(log['timestamp']).strftime(
                                '%H:%M:%S'
                            ),
                            log['step_name'],
                            f'[{"green" if log["log_type"] == "stdout" else "red"}]{log["log_type"]}[/]',
                            log['content'].strip(),
                        ),
                    )
                except (AttributeError, ValueError):
                    # Fallback to polling if registration not available
                    pass

                # Main loop - poll for updates
                while True:
                    # Check if there are still running pipelines
                    running = False
                    config = cast(Any, pipeline).PipelineConfig
                    if run_id:
                        running = run_id in config.running_pipelines
                    else:
                        for (
                            current_run_id,
                            pipeline_info,
                        ) in config.running_pipelines.items():
                            if pipeline_info['pipeline_name'] == pipeline_name:
                                running = True
                                break

                    # Update logs
                    update_logs()

                    # Exit if pipeline is no longer running
                    if not running:
                        # One final update
                        update_logs()
                        time.sleep(1)
                        header.add_row(
                            '[green]Pipeline execution completed[/]'
                        )
                        live.refresh()
                        time.sleep(2)
                        break

                    # Short sleep to avoid hammering the database
                    time.sleep(0.5)

            except KeyboardInterrupt:
                header.add_row('[yellow]Log following stopped by user[/]')
                live.refresh()
                time.sleep(1)
                return

        return

    # Regular log display (non-follow mode)
    logs = pipeline.get_pipeline_logs(
        run_id=run_id,
        pipeline_name=pipeline_name,
        step_name=step_name,
        limit=limit,
        log_type=log_type,
    )

    if not logs:
        console.print('[yellow]No logs found[/]')
        return

    table = _create_logs_table()
    highlighter = ReprHighlighter()

    for log in logs:
        timestamp = datetime.fromisoformat(log['timestamp']).strftime(
            '%Y-%m-%d %H:%M:%S'
        )
        content = log['content'].strip()
        log_style = 'green' if log['log_type'] == 'stdout' else 'red'

        text = Text(
            content[:MAX_CONTENT_LENGTH]
            + ('...' if len(content) > MAX_CONTENT_LENGTH else '')
        )
        if highlighter:
            try:
                highlighter.highlight(text)
            except Exception:
                # Ignore if highlighting fails
                pass

        table.add_row(
            log['pipeline_name'],
            log['step_name'],
            f'[{log_style}]{log["log_type"]}[/]',
            timestamp,
            text,
        )

    console.print(table)


def _handle_pipeline_history(
    makim_instance: Makim,
    pipeline_name: Optional[str] = None,
    limit: int = 10,
    status: Optional[str] = None,
    details: bool = False,
) -> None:
    """Handle viewing pipeline execution history.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    pipeline_name : Optional[str]
        Filter history by pipeline name.
    limit : int
        Number of most recent executions to show.
    status : Optional[str]
        Filter by status (running, completed, failed, cancelled).
    details : bool
        Show detailed step information.
    """
    console = Console()
    pipeline = cast(Any, makim_instance.pipeline)

    history = pipeline.get_pipeline_history(
        pipeline_name=pipeline_name, limit=limit, status=status
    )

    if not history:
        console.print('[yellow]No pipeline execution history found[/]')
        return

    table = _create_history_table()

    for run in history:
        # Calculate duration
        duration = 'N/A'
        if run['start_time'] and run['end_time']:
            start = datetime.fromisoformat(run['start_time'])
            end = datetime.fromisoformat(run['end_time'])
            duration = f'{(end - start).total_seconds():.2f}s'

        # Status styling
        status = run['status']
        status_style = ''
        if status == 'completed':
            status_style = 'green'
        elif status == 'failed':
            status_style = 'red'
        elif status == 'running':
            status_style = 'yellow'
        elif status == 'cancelled':
            status_style = 'red'

        # Format progress
        progress = f'{run["progress"]:.1f}%' if 'progress' in run else 'N/A'

        table.add_row(
            run['id'],
            run['pipeline_name'],
            f'[{status_style}]{status}[/]',
            progress,
            datetime.fromisoformat(run['start_time']).strftime(
                '%Y-%m-%d %H:%M:%S'
            ),
            'N/A'
            if not run['end_time']
            else datetime.fromisoformat(run['end_time']).strftime(
                '%Y-%m-%d %H:%M:%S'
            ),
            duration,
        )

    console.print(table)

    # Show more detailed information about steps if requested
    if details and history:
        console.print('\n[bold blue]Step Details:[/]')

        for run in history:
            if not run['steps']:
                continue

            console.print(
                f'\n[bold cyan]Pipeline:[/] {run["pipeline_name"]} '
                f'[dim]({run["id"]})[/]'
            )

            step_table = Table(
                title=f'Steps - {run["status"]}', box=box.ROUNDED
            )
            step_table.add_column('Step', style='cyan')
            step_table.add_column('Task', style='blue')
            step_table.add_column('Status', style='yellow')
            step_table.add_column('Duration', style='green')
            step_table.add_column('Exit Code', style='magenta')

            for step in run['steps']:
                # Calculate duration
                duration = 'N/A'
                if step.get('start_time') and step.get('end_time'):
                    start = datetime.fromisoformat(step['start_time'])
                    end = datetime.fromisoformat(step['end_time'])
                    duration = f'{(end - start).total_seconds():.2f}s'

                # Status styling
                status = step['status']
                status_style = ''
                if status == 'completed':
                    status_style = 'green'
                elif status == 'failed':
                    status_style = 'red'
                elif status == 'running':
                    status_style = 'yellow'
                elif status == 'skipped':
                    status_style = 'dim'

                step_table.add_row(
                    step['name'],
                    step['task'],
                    f'[{status_style}]{status}[/]',
                    duration,
                    str(step['exit_code'])
                    if step.get('exit_code') is not None
                    else 'N/A',
                )

            console.print(step_table)


def _handle_pipeline_schedule(
    makim_instance: Makim,
    pipeline_name: str,
    cron: Optional[str] = None,
    interval: Optional[int] = None,
) -> None:
    """Handle scheduling a pipeline.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    pipeline_name : str
        The name of the pipeline to schedule.
    cron : Optional[str]
        Cron expression for scheduling.
    interval : Optional[int]
        Interval in seconds between executions.
    """
    console = Console()
    pipeline = cast(Any, makim_instance.pipeline)

    if not cron and not interval:
        console.print(
            '[bold red]Error:[/] Either --cron or --interval must be specified'
        )
        raise typer.Exit(code=1)

    if cron and interval:
        console.print(
            '[bold red]Error:[/] Only one of --cron or --interval can be '
            'specified'
        )
        raise typer.Exit(code=1)

    success = pipeline.schedule_pipeline(
        pipeline_name, cron=cron, interval=interval
    )

    if success:
        if cron:
            console.print(
                f'[green]Pipeline scheduled successfully:[/] {pipeline_name} '
                f'with cron: {cron}'
            )
        else:
            console.print(
                f'[green]Pipeline scheduled successfully:[/] {pipeline_name} '
                f'with interval: {interval}s'
            )
    else:
        console.print(
            f'[bold red]Failed to schedule pipeline:[/] {pipeline_name}'
        )
        raise typer.Exit(code=1)


def _handle_pipeline_scheduled(makim_instance: Makim) -> None:
    """Handle listing scheduled pipelines.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    """
    console = Console()
    pipeline = cast(Any, makim_instance.pipeline)

    scheduled = pipeline.get_scheduled_pipelines()

    if not scheduled:
        console.print('[yellow]No scheduled pipelines found[/]')
        return

    table = _create_schedule_table()

    for sched in scheduled:
        schedule_value = sched['schedule_value']
        if sched['schedule_type'] == 'interval':
            schedule_value = f'Every {schedule_value} seconds'

        table.add_row(
            sched['id'],
            sched['pipeline_name'],
            schedule_value,
            sched['last_run_time'] or 'Never',
            sched['next_run_time'] or 'N/A',
            sched['status'],
        )

    console.print(table)


def _handle_pipeline_unschedule(
    makim_instance: Makim,
    pipeline_name: str,
) -> None:
    """Handle unscheduling a pipeline.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    pipeline_name : str
        The name of the pipeline to unschedule.
    """
    console = Console()
    pipeline = cast(Any, makim_instance.pipeline)

    success = pipeline.unschedule_pipeline(pipeline_name)

    if success:
        console.print(
            f'[green]Pipeline unscheduled successfully:[/] {pipeline_name}'
        )
    else:
        console.print(
            f'[bold red]Failed to unschedule pipeline:[/] {pipeline_name}'
        )
        raise typer.Exit(code=1)


def _handle_pipeline_retry(
    makim_instance: Makim,
    pipeline_name: str,
    all_steps: bool = False,
) -> None:
    """Handle retrying a failed pipeline.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    pipeline_name : str
        The name of the failed pipeline to retry.
    all_steps : bool
        If True, retry all steps, not just failed ones.
    """
    console = Console()
    pipeline = cast(Any, makim_instance.pipeline)

    success = pipeline.retry_failed_pipeline(
        pipeline_name, all_steps=all_steps
    )

    if success:
        console.print(f'[green]Pipeline retry successful:[/] {pipeline_name}')
    else:
        console.print(f'[bold red]Pipeline retry failed:[/] {pipeline_name}')
        raise typer.Exit(code=1)


def _handle_pipeline_cancel(
    makim_instance: Makim,
    pipeline_name: str,
) -> None:
    """Handle cancelling a running pipeline.

    Parameters
    ----------
    makim_instance : Makim
        The Makim instance.
    pipeline_name : str
        The name or ID of the running pipeline to cancel.
    """
    console = Console()
    pipeline = cast(Any, makim_instance.pipeline)

    success = pipeline.cancel_pipeline(pipeline_name)

    if success:
        console.print(
            f'[green]Pipeline cancellation requested:[/] {pipeline_name}'
        )
    else:
        console.print(
            f'[bold red]Failed to cancel pipeline:[/] {pipeline_name}'
        )
        raise typer.Exit(code=1)
