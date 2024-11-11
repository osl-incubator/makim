"""Manages scheduled tasks for Makim using APScheduler."""

import asyncio

from pathlib import Path
from typing import Any

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from makim.core import Makim
from makim.logs import MakimError, MakimLogs


class MakimScheduler:
    """Manages scheduled tasks for Makim using APScheduler."""

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
            self.makim.run({'task': task_name, **args})
        except Exception as e:
            MakimLogs.print_error(
                f'Error executing scheduled task {task_name}: {e!s}'
            )
        finally:
            loop.close()

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
        try:
            self.scheduler.add_job(
                func=self._execute_task,
                trigger='cron',
                args=[task_name, args or {}],
                id=job_id,
                **self._parse_schedule(schedule),
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

    def get_job_status(self, job_id: str) -> dict:
        """Get the status of a scheduled job."""
        job = self.scheduler.get_job(job_id)
        if not job:
            MakimLogs.raise_error(
                f"Job '{job_id}' not found", MakimError.SCHEDULER_JOB_NOT_FOUND
            )

        return {
            'id': job.id,
            'next_run': job.next_run_time,
            'schedule': str(job.trigger),
            'active': job.next_run_time is not None,
        }

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all scheduled jobs."""
        return [
            {
                'id': job.id,
                'next_run': job.next_run_time,
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

    def _parse_schedule(self, schedule: str) -> dict:
        """Parse schedule string into APScheduler arguments."""
        schedule = schedule.lower()

        if schedule in ('hourly', 'daily', 'weekly', 'monthly', 'yearly'):
            if schedule == 'hourly':
                return {'hour': '*'}
            elif schedule == 'daily':
                return {'day': '*'}
            elif schedule == 'weekly':
                return {'day_of_week': '0'}  # Sunday
            elif schedule == 'monthly':
                return {'day': '1'}
            elif schedule == 'yearly':
                return {'month': '1', 'day': '1'}

        # Handle cron expressions
        try:
            minute, hour, day, month, day_of_week = schedule.split()[:5]
            return {
                'minute': minute,
                'hour': hour,
                'day': day,
                'month': month,
                'day_of_week': day_of_week,
            }
        except ValueError:
            MakimLogs.raise_error(
                f'Invalid schedule format: {schedule}',
                MakimError.SCHEDULER_INVALID_SCHEDULE,
            )
