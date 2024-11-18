"""Manages scheduled tasks for Makim using APScheduler."""

import asyncio

from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from croniter import croniter

from makim.core import Makim
from makim.logs import MakimError, MakimLogs


class MakimScheduler:
    """Manages scheduled tasks for Makim using APScheduler."""

    _instance = None  # Singleton pattern for scheduler instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MakimScheduler, cls).__new__(cls)
        return cls._instance

    def __init__(self, makim_instance: 'Makim'):
        self.makim = makim_instance
        self.db_path = Path.home() / '.makim' / 'jobs.db'
        self._ensure_db_directory()

        # Configure job stores and executors
        jobstores = {
            'default': SQLAlchemyJobStore(url=f'sqlite:///{self.db_path}')
        }
        executors = {'default': ThreadPoolExecutor(20)}

        # Initialize scheduler with SQLite storage
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults={'coalesce': False, 'max_instances': 3},
        )

        # Listen for job events
        self.scheduler.add_listener(
            self._log_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

    def _ensure_db_directory(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _execute_task(self, task_name: str, args: dict) -> None:
        """Execute a Makim task within the scheduler."""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the task
            default_args = self.makim.global_data.get('default_args', {})
            merged_args = {**default_args, **(args or {})}
            self.makim.run({'task': task_name, **merged_args})
        except Exception as e:
            MakimLogs.print_error(
                f'Error executing scheduled task {task_name}: {e!s}'
            )
        finally:
            loop.close()

    def _log_job_event(self, event) -> None:
        """Log job execution success or failure."""
        job = self.scheduler.get_job(event.job_id)
        if event.exception:
            MakimLogs.print_error(f'Job {job.id} failed: {event.exception}')
        else:
            MakimLogs.print_info(f'Job {job.id} executed successfully.')

    def _validate_and_parse_schedule(self, schedule: str) -> dict:
        """Validate and parse cron expressions."""
        try:
            # Use croniter to validate and compute next run time
            base_time = datetime.now()
            iter = croniter(schedule, base_time)

            # Get parsed schedule for APScheduler
            next_time = iter.get_next(datetime)
            cron_params = {
                'minute': iter.next_exact('minute'),
                'hour': iter.next_exact('hour'),
                'day': iter.next_exact('day'),
                'month': iter.next_exact('month'),
                'day_of_week': iter.next_exact('weekday'),
            }
            return cron_params
        except ValueError:
            MakimLogs.raise_error(
                f'Invalid cron expression: {schedule}',
                MakimError.SCHEDULER_INVALID_SCHEDULE,
            )

    def add_job(
        self,
        job_id: str,
        task_name: str,
        schedule: str,
        args: dict[Any, Any] = None,
    ) -> None:
        """
        Add a new scheduled job.

        Parameters
        ----------
        job_id : str
            Unique identifier for the job
        task_name : str
            Name of the Makim task to execute
        schedule : str
            Cron schedule expression
        args : dict[Any, Any], optional
            Arguments to pass to the task
        """
        cron_params = self._validate_and_parse_schedule(schedule)
        try:
            self.scheduler.add_job(
                func=self._execute_task,
                trigger='cron',
                args=[task_name, args or {}],
                id=job_id,
                **cron_params,
                replace_existing=True,
            )
            MakimLogs.print_info(f"Successfully scheduled job '{job_id}'")
        except Exception as e:
            MakimLogs.raise_error(
                f"Failed to schedule job '{job_id}': {e!s}",
                MakimError.SCHEDULER_JOB_ERROR,
            )

    def remove_job(self, job_id: str) -> None:
        """Remove a scheduled job."""
        try:
            self.scheduler.remove_job(job_id)
            MakimLogs.print_info(f"Successfully removed job '{job_id}'")
        except Exception as e:
            MakimLogs.raise_error(
                f"Failed to remove job '{job_id}': {e!s}",
                MakimError.SCHEDULER_JOB_ERROR,
            )

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all scheduled jobs."""
        return [
            {
                'id': job.id,
                'next_run': job.next_run_time,
                'last_run': job.last_run_time,  # Include last run
                'schedule': str(job.trigger),
            }
            for job in self.scheduler.get_jobs()
        ]

    def start(self) -> None:
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
