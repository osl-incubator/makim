"""Module for handling task scheduling in Makim."""

from __future__ import annotations

import json
import shlex
import subprocess  # nosec B404 - subprocess is required for task execution

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, cast

from apscheduler.job import Job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from makim.logs import MakimError, MakimLogs


class Config:
    """Global configuration state handler."""

    config_file: Optional[str] = None
    job_history_path: Optional[Path] = None


def init_globals(config_file: str, history_path: Path) -> None:
    """
    Initialize global variables needed for job execution.

    Parameters
    ----------
    config_file : str
        Path to the configuration file.
    history_path : Path
        Path to the job history file.
    """
    Config.config_file = config_file
    Config.job_history_path = history_path


def _sanitize_command(cmd_list: list[str]) -> list[str]:
    """
    Sanitize command arguments to prevent command injection.

    Parameters
    ----------
    cmd_list : list of str
        List of command arguments.

    Returns
    -------
    list of str
        Sanitized list of command arguments.
    """
    return [shlex.quote(str(arg)) for arg in cmd_list]


def log_execution(
    name: str,
    event: str,
    result: Optional[str] = None,
    error: Optional[str] = None,
    task: Optional[str] = None,
) -> None:
    """
    Log execution details.

    Parameters
    ----------
    name : str
        The scheduler name.
    event : str
        Event type ('scheduled', 'execution_completed', 'execution_failed').
    result : Optional[str], optional
        Output from task execution, by default None.
    error : Optional[str], optional
        Error message if execution failed, by default None.
    task : Optional[str], optional
        Associated task name, by default None.
    """
    if Config.job_history_path is None:
        MakimLogs.print_warning(
            'Unable to log job execution: Job history path not configured'
        )
        return

    try:
        if Config.job_history_path.exists():
            with open(Config.job_history_path, 'r') as f:
                history = json.load(f)
        else:
            history = {}

        current_time = datetime.now().isoformat()

        if name not in history:
            history[name] = []

        execution_entry = {
            'scheduled_timestamp': current_time,
            'event': event,
            'execution_timestamp': None,
            'output': None,
            'error': None,
            'task': task,
        }

        if event != 'scheduled':
            execution_entry.update(
                {
                    'execution_timestamp': current_time,
                    'output': result,
                    'error': error,
                }
            )
            if history[name]:
                last_scheduled = next(
                    (
                        entry
                        for entry in reversed(history[name])
                        if entry['event'] == 'scheduled'
                    ),
                    None,
                )
                if last_scheduled:
                    execution_entry['scheduled_timestamp'] = last_scheduled[
                        'scheduled_timestamp'
                    ]
        history[name].append(execution_entry)

        with open(Config.job_history_path, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception:
        MakimLogs.print_warning('Failed to save job history')


def run_makim_task(
    task: str, scheduler_name: str, args: Optional[Dict[str, Any]] = None
) -> None:
    """
    Execute a Makim task.

    Parameters
    ----------
    task : str
        The task to execute.
    scheduler_name : str
        The name of the scheduler that triggered this task.
    args : Optional[Dict[str, Any]], optional
        Optional arguments for the task, by default None.
    """
    if Config.config_file is None:
        MakimLogs.raise_error(
            (
                'Scheduled task cannot run because the configuration file is '
                'not specified'
            ),
            MakimError.SCHEDULER_JOB_ERROR,
        )

    if Config.job_history_path is None:
        MakimLogs.print_warning('Job history logging is disabled')

    cmd: list[str] = ['makim', '--file', Config.config_file or '', task]
    if args:
        for key, value in args.items():
            safe_key = str(key)
            if isinstance(value, bool):
                if value:
                    cmd.append(f'--{safe_key}')
            else:
                cmd.extend([f'--{safe_key}', str(value)])
    safe_cmd = _sanitize_command(cmd)

    try:
        result = subprocess.run(
            safe_cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        log_execution(
            scheduler_name, 'execution_completed', result=result.stdout
        )
    except subprocess.CalledProcessError as e:
        error_msg = f'Job execution failed with return code {e.returncode}'
        log_execution(scheduler_name, 'execution_failed', error=error_msg)
        MakimLogs.raise_error(
            f"Scheduled task '{task}' failed to execute",
            MakimError.SCHEDULER_JOB_ERROR,
        )


class MakimScheduler:
    """
    Handles task scheduling for Makim.

    Parameters
    ----------
    makim_instance : Makim
        Makim instance containing configuration details.
    """

    def __init__(self, makim_instance: Any):
        """
        Initialize the scheduler with configuration.

        Parameters
        ----------
        makim_instance : Makim
            Instance containing configuration details.
        """
        self.config_file = makim_instance.file
        self.scheduler: Optional[BackgroundScheduler] = None
        self.job_store_path = Path.home() / '.makim' / 'jobs.sqlite'
        self.job_history_path = Path.home() / '.makim' / 'history.json'
        self._setup_directories()
        self._initialize_scheduler()
        self.job_history: dict[str, list[Dict[str, Any]]] = (
            self._load_history()
        )

        init_globals(self.config_file, self.job_history_path)

        self._sync_jobs_with_config(
            makim_instance.global_data.get('scheduler', {})
        )

    def _sync_jobs_with_config(self, config_jobs: Dict[str, Any]) -> None:
        """
        Synchronize scheduler jobs with current config file.

        Parameters
        ----------
        config_jobs : dict
            Dictionary of scheduled jobs from the configuration.
        """
        if not self.scheduler:
            MakimLogs.print_warning(
                'Scheduler synchronization skipped: Scheduler not initialized'
            )
            return

        current_job_ids = {job.id for job in self.scheduler.get_jobs()}
        config_job_ids = set(config_jobs.keys())

        for job_id in current_job_ids - config_job_ids:
            self.scheduler.remove_job(job_id)

        self.job_history = {
            name: history
            for name, history in self.job_history.items()
            if name in config_job_ids
        }
        self._save_history()

    def _setup_directories(self) -> None:
        """Create necessary directories for job storage."""
        try:
            self.job_store_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            MakimLogs.raise_error(
                f'Cannot create scheduler directory at '
                f'{self.job_store_path.parent}. Please check your permissions',
                MakimError.SCHEDULER_JOB_ERROR,
            )
        except Exception:
            MakimLogs.raise_error(
                'Failed to create scheduler directory',
                MakimError.SCHEDULER_JOB_ERROR,
            )

    def _initialize_scheduler(self) -> None:
        """Initialize the APScheduler with SQLite backend."""
        try:
            jobstores = {
                'default': SQLAlchemyJobStore(
                    url=f'sqlite:///{self.job_store_path}'
                )
            }
            self.scheduler = BackgroundScheduler(jobstores=jobstores)
            if self.scheduler is not None:
                self.scheduler.start()
        except Exception:
            MakimLogs.raise_error(
                'Could not initialize the scheduler database',
                MakimError.SCHEDULER_JOB_ERROR,
            )

    def _load_history(self) -> dict[str, list[Dict[str, Any]]]:
        """
        Load job execution history from file.

        Returns
        -------
        dict
            Dictionary of job execution history.
        """
        try:
            if self.job_history_path.exists():
                with open(self.job_history_path, 'r') as f:
                    loaded_history = json.load(f)
                    if not isinstance(loaded_history, dict):
                        MakimLogs.print_warning(
                            'Invalid job history format, resetting history'
                        )
                        return {}
                    return cast(
                        dict[str, list[Dict[str, Any]]], loaded_history
                    )
        except Exception:
            MakimLogs.print_warning('Could not load job history')
        return {}

    def _save_history(self) -> None:
        """Save job execution history to file."""
        try:
            with open(self.job_history_path, 'w') as f:
                json.dump(self.job_history, f)
        except Exception:
            MakimLogs.print_warning('Could not save job history')

    def add_job(
        self,
        name: str,
        schedule: str,
        task: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a new scheduled job.

        Parameters
        ----------
        name : str
            The name of the job.
        schedule : str
            Cron expression defining job schedule.
        task : str
            The task to be executed.
        args : dict, optional
            Additional arguments for the task, by default None.
        """
        if self.scheduler is None:
            MakimLogs.raise_error(
                'Cannot add job: Scheduler system is not available',
                MakimError.SCHEDULER_JOB_ERROR,
            )
            return

        try:
            trigger = CronTrigger.from_crontab(schedule)
            log_execution(name, 'scheduled', task=task)

            self.scheduler.add_job(
                func='makim.scheduler:run_makim_task',
                trigger=trigger,
                args=[task, name],
                kwargs={'args': args or {}},
                id=name,
                name=name,
                replace_existing=True,
                misfire_grace_time=None,
            )
            MakimLogs.print_info(
                f"Successfully scheduled job '{name}' to run task '{task}'"
            )
        except ValueError:
            MakimLogs.raise_error(
                f"Invalid cron schedule format for job '{name}'",
                MakimError.SCHEDULER_INVALID_SCHEDULE,
            )
        except Exception:
            log_execution(
                name, 'schedule_failed', error='Failed to schedule job'
            )
            MakimLogs.raise_error(
                f"Failed to schedule job '{name}'",
                MakimError.SCHEDULER_JOB_ERROR,
            )

    def remove_job(self, name: str) -> None:
        """
        Remove a scheduled job.

        Parameters
        ----------
        name : str
            The name of the job to remove.
        """
        if self.scheduler is None:
            MakimLogs.raise_error(
                'Cannot remove job: Scheduler system is not available',
                MakimError.SCHEDULER_JOB_ERROR,
            )
            return

        job = self.get_job(name)
        if not job:
            MakimLogs.raise_error(
                f"Job '{name}' does not exist",
                MakimError.SCHEDULER_JOB_NOT_FOUND,
            )

        try:
            self.scheduler.remove_job(name)
            log_execution(name, 'removed')
            MakimLogs.print_info(
                f"Successfully removed scheduled job '{name}'"
            )
        except Exception:
            log_execution(name, 'remove_failed', error='Failed to remove job')
            MakimLogs.raise_error(
                f"Failed to remove job '{name}'",
                MakimError.SCHEDULER_JOB_ERROR,
            )

    def get_job(self, name: str) -> Optional[Job]:
        """
        Get a job by name.

        Parameters
        ----------
        name : str
            The name of the job.

        Returns
        -------
        Job or None
            The job object if found, otherwise None.
        """
        if self.scheduler is None:
            MakimLogs.raise_error(
                'Cannot retrieve job: Scheduler system is not available',
                MakimError.SCHEDULER_JOB_ERROR,
            )
            return None

        job = self.scheduler.get_job(name)
        if not job:
            MakimLogs.print_warning(f"Job '{name}' not found")
        return job

    def list_jobs(self) -> list[Dict[str, Any]]:
        """
        List all scheduled jobs.

        Returns
        -------
        list of dict
            A list of dictionaries containing job details.
        """
        if self.scheduler is None:
            MakimLogs.raise_error(
                'Cannot list jobs: Scheduler system is not available',
                MakimError.SCHEDULER_JOB_ERROR,
            )
            return []

        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                job_info = {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat()
                    if job.next_run_time
                    else None,
                    'schedule': str(job.trigger),
                }
                jobs.append(job_info)
            return jobs
        except Exception:
            MakimLogs.raise_error(
                'Failed to retrieve job list', MakimError.SCHEDULER_JOB_ERROR
            )
            return []
