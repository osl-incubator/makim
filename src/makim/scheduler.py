from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.job import Job

class MakimScheduler:
    """Handles task scheduling for Makim."""

    def __init__(self, makim_instance: Any):
        """Initialize the scheduler with configuration."""
        self.config_file = makim_instance.file
        self.scheduler = None
        self.job_store_path = Path.home() / '.makim' / 'jobs.sqlite'
        self.job_history_path = Path.home() / '.makim' / 'history.json'
        self._setup_directories()
        self._initialize_scheduler()
        self.job_history: Dict[str, list[Dict[str, Any]]] = self._load_history()

    def _setup_directories(self) -> None:
        """Create necessary directories for job storage."""
        self.job_store_path.parent.mkdir(parents=True, exist_ok=True)
        
    def _initialize_scheduler(self) -> None:
        """Initialize the APScheduler with SQLite backend."""
        jobstores = {
            'default': SQLAlchemyJobStore(url=f'sqlite:///{self.job_store_path}')
        }
        self.scheduler = BackgroundScheduler(jobstores=jobstores)
        self.scheduler.start()

    def _load_history(self) -> Dict[str, list[Dict[str, Any]]]:
        """Load job execution history from file."""
        if self.job_history_path.exists():
            with open(self.job_history_path, 'r') as f:
                return json.load(f)
        return {}

    def _save_history(self) -> None:
        """Save job execution history to file."""
        with open(self.job_history_path, 'w') as f:
            json.dump(self.job_history, f)

    def _log_execution(self, name: str, event: str, result: Optional[str] = None, error: Optional[str] = None) -> None:
        """Log execution details to history."""
        if name not in self.job_history:
            self.job_history[name] = []
            
        self.job_history[name].append({
            'timestamp': datetime.now().isoformat(),
            'event': event,
            'result': result,
            'error': error
        })
        self._save_history()

    @staticmethod
    def _run_makim_task(config_file: str, task: str, args: Dict[str, Any]) -> None:
        """Static method to execute a Makim task."""
        cmd = ['makim', '--file', config_file, task]
        
        # Convert args to command line arguments
        for key, value in (args or {}).items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f'--{key}')
            else:
                cmd.extend([f'--{key}', str(value)])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise Exception(f"Job execution failed: {e.stderr}")

    def add_job(self, name: str, schedule: str, task: str, args: Optional[Dict[str, Any]] = None) -> None:
        """Add a new scheduled job."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")

        try:
            # Create trigger from schedule
            trigger = CronTrigger.from_crontab(schedule)
            
            # Add the job using the static method
            self.scheduler.add_job(
                func=self._run_makim_task,
                trigger=trigger,
                args=[self.config_file, task, args or {}],
                id=name,
                name=name,
                replace_existing=True,
                misfire_grace_time=None
            )
            
            self._log_execution(name, 'scheduled')
            
        except Exception as e:
            self._log_execution(name, 'schedule_failed', error=str(e))
            raise

    def remove_job(self, name: str) -> None:
        """Remove a scheduled job."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        try:
            self.scheduler.remove_job(name)
            self._log_execution(name, 'removed')
        except Exception as e:
            self._log_execution(name, 'remove_failed', error=str(e))
            raise

    def get_job(self, name: str) -> Optional[Job]:
        """Get a job by name."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        return self.scheduler.get_job(name)

    def list_jobs(self) -> list[Dict[str, Any]]:
        """List all scheduled jobs."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        jobs = []
        for job in self.scheduler.get_jobs():
            job_info = {
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'schedule': str(job.trigger),
            }
            jobs.append(job_info)
        return jobs

    def get_job_status(self, name: str) -> Dict[str, Any]:
        """Get detailed status of a specific job."""
        job = self.get_job(name)
        if not job:
            return {'error': 'Job not found'}

        history = self.job_history.get(name, [])
        
        return {
            'name': name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'schedule': str(job.trigger),
            'history': history
        }

    def shutdown(self) -> None:
        """Shutdown the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()