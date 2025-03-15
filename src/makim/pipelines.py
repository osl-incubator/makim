from __future__ import annotations

import sqlite3
import typer
import threading
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict, TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# 🚀 Fix Circular Import: Import `Makim` only for type checking
if TYPE_CHECKING:
    from makim.core import Makim
def run_scheduled_pipeline(name: str):
    """Global function to execute scheduled pipelines (used by APScheduler)."""
    from makim.pipelines import MakimPipelineEngine  # Import inside function to avoid circular imports

    print(f"🔍 [GLOBAL] Running scheduled pipeline: {name}")

    engine = MakimPipelineEngine(config_file="makim.yaml")

    try:
        steps = engine.get_pipeline_steps(name)
        if not steps:
            raise ValueError(f"Pipeline '{name}' has no steps defined.")

        engine.run_pipeline(name, steps)

        # ✅ Log execution
        engine.log_pipeline_execution(name, "scheduled-execution", "success")
        print(f"✅ [GLOBAL] Successfully ran scheduled pipeline: {name}")

    except Exception as e:
        error_msg = str(e)
        print(f"❌ [GLOBAL] Scheduled pipeline '{name}' failed: {error_msg}")
        engine.log_pipeline_execution(name, "scheduled-execution", "failed", error=error_msg)

class MakimPipelineEngine:
    """
    Handles pipeline execution, logging, and management in Makim.
    """

    def __init__(self, config_file: str):
        self.config_file = config_file
        self.db_path = Path.home() / ".makim" / "pipelines.sqlite"
        self._init_paths()

        self.scheduler = BackgroundScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{self.db_path}")},
        )
        self.scheduler.start()

        self._initialize_database()

    def _init_paths(self):
        """Ensure necessary directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _initialize_database(self):
        """Create the SQLite database and ensure the required table exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_name TEXT,
                step TEXT,
                status TEXT,  -- pending, running, success, failed
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                output TEXT,
                error TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_name TEXT UNIQUE,
                cron_expression TEXT,
                interval_seconds INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def run_pipeline(self, name: str, steps: List[Dict[str, Any]]) -> None:
        """
        Run a pipeline and log execution results.
        """
        from makim.core import Makim  # 🚀 Fix Circular Import: Import inside function

        def run_task(task):
            retries = task.get("retries", 0)
            last_exception = None  # ✅ Store last exception for logging

            for attempt in range(retries + 1):
                try:
                    makim_instance = Makim()
                    makim_instance.load(self.config_file)
                    output = makim_instance.run({"task": task["target"], **task.get("args", {})})

                    # ✅ Log successful execution
                    self.log_pipeline_execution(name, task["target"], "success", output=output)
                    return
                except Exception as e:
                    last_exception = str(e)
                    if attempt < retries:
                        print(f"Retrying {task['target']} (attempt {attempt + 1}/{retries})")

            # ✅ Ensure logging even if all retries fail
            self.log_pipeline_execution(name, task["target"], "failed", error=last_exception)

        threads = []
        for task in steps:
            thread = threading.Thread(target=run_task, args=(task,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()


    def log_pipeline_execution(
        self, pipeline_name: str, step: str, status: str, output: Optional[str] = None, error: Optional[str] = None
    ) -> None:
        """Log execution of pipeline steps into SQLite (including scheduled executions)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        print(f"🔍 LOGGING EXECUTION: {pipeline_name} - {step} - {status}")  # ✅ Debugging output

        cursor.execute("""
            INSERT INTO pipeline_runs (pipeline_name, step, status, output, error)
            VALUES (?, ?, ?, ?, ?)
        """, (pipeline_name, step, status, output or "N/A", error or "N/A"))  # ✅ Ensure output is not None

        conn.commit()
        conn.close()


    def get_pipeline_logs(self, pipeline_name: Optional[str] = None, limit: int = 10):
        """Retrieve execution logs for a specific pipeline."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT pipeline_name, step, status, timestamp, output, error FROM pipeline_runs ORDER BY timestamp DESC LIMIT ?"
        params = (limit,)

        if pipeline_name:
            query = "SELECT pipeline_name, step, status, timestamp, output, error FROM pipeline_runs WHERE pipeline_name = ? ORDER BY timestamp DESC LIMIT ?"
            params = (pipeline_name, limit)

        cursor.execute(query, params)
        logs = cursor.fetchall()
        conn.close()

        return logs

    def list_pipelines(self) -> List[Dict[str, Any]]:
        """Retrieve the list of defined pipelines from the Makim configuration."""
        from makim.core import Makim  # 🚀 Fix Circular Import: Import inside function

        makim_instance = Makim()
        makim_instance.load(self.config_file)

        pipelines = makim_instance.global_data.get("pipelines", {})

        return [
            {
                "name": name,
                "tasks": len(data.get("tasks", [])),
                "help": data.get("help", "—"),
            }
            for name, data in pipelines.items()
        ]

    def get_pipeline_structure(self, name: str) -> List[str]:
        """Retrieve the structure of a pipeline as a list of tasks."""
        from makim.core import Makim  # 🚀 Fix Circular Import: Import inside function

        makim_instance = Makim()
        makim_instance.load(self.config_file)

        pipeline = makim_instance.global_data.get("pipelines", {}).get(name)
        if not pipeline:
            raise ValueError(f"Pipeline '{name}' not found.")

        return [task["target"] for task in pipeline.get("tasks", [])]

    def clear_pipeline_logs(self, pipeline_name: Optional[str] = None) -> None:
        """Clear logs for a specific pipeline or all logs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if pipeline_name:
            cursor.execute("DELETE FROM pipeline_runs WHERE pipeline_name = ?", (pipeline_name,))
        else:
            cursor.execute("DELETE FROM pipeline_runs")

        conn.commit()
        conn.close()

    def schedule_pipeline(self, name: str, cron_expression: Optional[str] = None, interval_seconds: Optional[int] = None):
        """Schedule a pipeline using either a cron expression or an interval."""
        import makim.core  # ✅ Import inside function to prevent circular import
        from makim.core import Makim  # ✅ Ensure Makim is properly referenced
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        makim_instance = Makim()
        makim_instance.load(self.config_file)

        pipelines = makim_instance.global_data.get("pipelines", {})
        if name not in pipelines:
            raise ValueError(f"Pipeline '{name}' not found.")

        cursor.execute("""
            INSERT OR REPLACE INTO pipeline_schedules (pipeline_name, cron_expression, interval_seconds)
            VALUES (?, ?, ?)
        """, (name, cron_expression, interval_seconds))

        conn.commit()
        conn.close()

        if cron_expression:
            trigger = CronTrigger.from_crontab(cron_expression)
        elif interval_seconds:
            trigger = IntervalTrigger(seconds=interval_seconds)
        else:
            raise ValueError("Either a cron expression or an interval must be provided.")
        from makim.pipelines import run_scheduled_pipeline
        # ✅ Use global function instead of `self.run_scheduled_pipeline`
        self.scheduler.add_job(run_scheduled_pipeline, trigger, args=[name], id=name, replace_existing=True)

        print(f"✅ Scheduled pipeline '{name}' successfully.")

    def run_scheduled_pipeline(self, name: str):
        """Run a scheduled pipeline from the database and log its execution."""
        print(f"🔍 [CLASS] Running scheduled pipeline: {name}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT pipeline_name FROM pipeline_schedules WHERE pipeline_name = ?", (name,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            print(f"❌ [CLASS] Scheduled pipeline '{name}' not found in database.")
            return

        try:
            makim_instance = Makim()
            makim_instance.load(self.config_file)

            pipeline = makim_instance.global_data.get("pipelines", {}).get(name)
            if not pipeline:
                raise ValueError(f"Pipeline '{name}' not found in config.")

            print(f"🔍 [CLASS] Running scheduled pipeline tasks: {pipeline['steps']}")
            self.log_pipeline_execution(name, "scheduled-execution", "running")  # ✅ Log start
            self.run_pipeline(name, pipeline["steps"])
            self.log_pipeline_execution(name, "scheduled-execution", "success")  # ✅ Log success

        except Exception as e:
            error_msg = str(e)
            print(f"❌ [CLASS] Scheduled pipeline '{name}' failed: {error_msg}")
            self.log_pipeline_execution(name, "scheduled-execution", "failed", error=error_msg)



    def list_scheduled_pipelines(self):
        """List all scheduled pipelines."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT pipeline_name, cron_expression, interval_seconds FROM pipeline_schedules")
        schedules = cursor.fetchall()

        conn.close()
        return schedules

    def remove_scheduled_pipeline(self, name: str):
        """Remove a scheduled pipeline."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM pipeline_schedules WHERE pipeline_name = ?", (name,))
        conn.commit()
        conn.close()

        self.scheduler.remove_job(name)
        print(f"❌ Removed scheduled pipeline '{name}'.")

    def unschedule_pipeline(self, name: str):
        """Remove a scheduled pipeline from SQLite and APScheduler."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if the pipeline is scheduled
        cursor.execute("SELECT pipeline_name FROM pipeline_schedules WHERE pipeline_name = ?", (name,))
        row = cursor.fetchone()

        if not row:
            typer.echo(f"❌ Pipeline '{name}' is not scheduled.")
            conn.close()
            return

        # Remove from SQLite
        cursor.execute("DELETE FROM pipeline_schedules WHERE pipeline_name = ?", (name,))
        conn.commit()
        conn.close()

        # Remove from APScheduler
        try:
            self.scheduler.remove_job(name)
            typer.echo(f"✅ Unscheduled pipeline '{name}' successfully.")
        except Exception:
            typer.echo(f"⚠️ Pipeline '{name}' was not found in APScheduler, but removed from the database.")

    def get_pipeline_status(self):
        """Retrieve the status of scheduled and running pipelines."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # ✅ Get scheduled pipelines from SQLite
        cursor.execute("SELECT pipeline_name, cron_expression, interval_seconds FROM pipeline_schedules")
        scheduled_pipelines = cursor.fetchall()

        # ✅ Get running jobs from APScheduler
        running_jobs = self.scheduler.get_jobs()

        # ✅ Get last 5 pipeline executions
        cursor.execute("""
            SELECT pipeline_name, step, status, timestamp 
            FROM pipeline_runs 
            ORDER BY timestamp DESC LIMIT 5
        """)
        recent_executions = cursor.fetchall()

        conn.close()

        return {
            "scheduled": scheduled_pipelines,
            "running": running_jobs,
            "recent_executions": recent_executions,
        }

    def retry_pipeline(self, name: str):
        """Retries the last failed execution of a pipeline."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # ✅ Find the last failed execution for this pipeline
        cursor.execute("""
            SELECT step FROM pipeline_runs 
            WHERE pipeline_name = ? AND status = 'failed' 
            ORDER BY timestamp DESC LIMIT 1
        """, (name,))
        row = cursor.fetchone()

        if not row:
            typer.echo(f"❌ No failed executions found for pipeline '{name}'.")
            conn.close()
            return

        failed_step = row[0]
        conn.close()

        # ✅ Run the failed step again
        typer.echo(f"🔄 Retrying failed step '{failed_step}' for pipeline '{name}'...")
        self.run_pipeline(name, [{"target": failed_step}])  # ✅ Retry only the failed step


    def cancel_pipeline(self, name: str):
        """Cancels a running pipeline in APScheduler."""
        try:
            self.scheduler.remove_job(name)  # ✅ Remove from scheduler
            typer.echo(f"❌ Pipeline '{name}' has been canceled.")
        except Exception:
            typer.echo(f"⚠️ No running job found for pipeline '{name}'.")

    def get_pipeline_history(self, name: Optional[str] = None, limit: int = 10):
        """Retrieve execution history for a specific pipeline or all pipelines."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # ✅ Get history for a specific pipeline or all pipelines
        if name:
            cursor.execute("""
                SELECT pipeline_name, step, status, timestamp 
                FROM pipeline_runs WHERE pipeline_name = ? 
                ORDER BY timestamp DESC LIMIT ?
            """, (name, limit))
        else:
            cursor.execute("""
                SELECT pipeline_name, step, status, timestamp 
                FROM pipeline_runs ORDER BY timestamp DESC LIMIT ?
            """, (limit,))

        history = cursor.fetchall()
        conn.close()
        print(f"🔍 HISTORY RESULT: {history}")
        return history


    def retry_all_failed(self, name: str):
        """Retries all failed executions of a pipeline."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # ✅ Find all failed steps for this pipeline
        cursor.execute("""
            SELECT step FROM pipeline_runs 
            WHERE pipeline_name = ? AND status = 'failed' 
            ORDER BY timestamp DESC
        """, (name,))
        rows = cursor.fetchall()

        if not rows:
            typer.echo(f"❌ No failed executions found for pipeline '{name}'.")
            conn.close()
            return

        failed_steps = [row[0] for row in rows]
        conn.close()

        # ✅ Run all failed steps again
        typer.echo(f"🔄 Retrying {len(failed_steps)} failed steps for pipeline '{name}'...")
        steps_to_retry = [{"target": step} for step in failed_steps]
        self.run_pipeline(name, steps_to_retry)


    def run_pipeline_sequential(
        self, name: str, steps: List[Dict[str, Any]], debug: bool = False, dry_run: bool = False
    ) -> None:
        """Execute pipeline steps sequentially with dry-run support."""
        from makim.core import Makim  # Fix circular import

        for step in steps:
            target = step["target"]
            args = step.get("args", {})

            if debug:
                print(f"🔍 DEBUG: Running step '{target}' with args {args} (Sequential Mode)")

            if dry_run:
                print(f"🛑 DRY-RUN: Skipping execution of step '{target}'")
                self.log_pipeline_execution(name, target, "dry-run")
                continue

            try:
                makim_instance = Makim()
                makim_instance.load(self.config_file)
                output = makim_instance.run({"task": target, **args})
                self.log_pipeline_execution(name, target, "success", output=output)
            except Exception as e:
                self.log_pipeline_execution(name, target, "failed", error=str(e))
                typer.echo(f"❌ Error in step '{target}': {e}")

    def run_pipeline_parallel(
    self, name: str, steps: List[Dict[str, Any]], debug: bool = False, 
    max_workers: Optional[int] = None, dry_run: bool = False
) -> None:
        """Execute pipeline steps in parallel with debug logging and worker limit."""
        from makim.core import Makim  # Fix circular import

        def run_task(step):
            target = step["target"]
            args = step.get("args", {})

            if debug:
                print(f"🔍 DEBUG: Running step '{target}' with args {args} (Parallel Mode)")

            if dry_run:
                print(f"🛑 DRY-RUN: Skipping execution of step '{target}'")
                self.log_pipeline_execution(name, target, "dry-run")
                return

            try:
                makim_instance = Makim()
                makim_instance.load(self.config_file)
                output = makim_instance.run({"task": target, **args})
                self.log_pipeline_execution(name, target, "success", output=output)
            except Exception as e:
                self.log_pipeline_execution(name, target, "failed", error=str(e))
                typer.echo(f"❌ Error in step '{target}': {e}")

        # ✅ Set max_workers (default: number of steps)
        max_threads = max_workers if max_workers else len(steps)  # Default: run all in parallel

        if debug:
            print(f"🔍 [DEBUG] Running {len(steps)} steps in parallel with {max_threads} workers...")

        # ✅ Use ThreadPoolExecutor for better thread management
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            executor.map(run_task, steps)
