"""Module for handling pipeline execution in Makim."""

from __future__ import annotations

import concurrent.futures
import shlex
import sqlite3
import subprocess  # nosec B404 - subprocess is required for task execution
import threading
import time

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, cast

import networkx as nx

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from rich import box
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.tree import Tree

# Constants for progress tracking and display
MAX_PROGRESS = 0.9  # Maximum progress for incremental updates
PROGRESS_INCREMENT = 0.1  # Progress increment per update
MAX_LOG_ROWS = 500  # Maximum number of log rows to display
MAX_CONTENT_LENGTH = 200  # Maximum length of content to display


class PipelineConfig:
    """Global configuration state handler for pipelines."""

    config_file: Optional[str] = None
    base_dir: Optional[Path] = None
    db_path: Optional[Path] = None
    running_pipelines: Dict[str, Dict[str, Any]] = {}
    log_listeners: Dict[str, List[Callable[..., Any]]] = {}


@dataclass
class PipelineStep:
    """Represents a step in a pipeline."""

    id: str
    name: str
    task: str
    args: Dict[str, Any]
    condition: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    retry_config: Dict[str, int] = field(default_factory=dict)
    timeout: Optional[int] = None
    status: str = 'pending'  # pending, running, completed, failed, skipped
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attempt: int = 0
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    progress: float = 0.0  # 0.0 to 1.0 for progress tracking


@dataclass
class PipelineRun:
    """Represents a pipeline execution."""

    id: str
    pipeline_name: str
    status: str  # running, completed, failed, cancelled
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_mode: str = 'sequential'
    steps: Dict[str, PipelineStep] = field(default_factory=dict)
    max_workers: int = 4
    progress: float = 0.0  # 0.0 to 1.0 for overall progress


def init_pipeline_globals(config_file: str) -> None:
    """
    Initialize global variables needed for pipeline execution.

    Parameters
    ----------
    config_file : str
        Path to the configuration file.
    """
    PipelineConfig.config_file = config_file
    PipelineConfig.base_dir = Path.home() / '.makim'
    PipelineConfig.db_path = PipelineConfig.base_dir / 'pipelines.sqlite'

    # Ensure directory exists
    PipelineConfig.base_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database
    _init_database()


def _init_database() -> None:
    """Initialize the SQLite database for storing pipeline execution data."""
    if not PipelineConfig.db_path:
        raise RuntimeError('Database path not initialized')

    # Create directory if it doesn't exist
    PipelineConfig.db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(PipelineConfig.db_path))
    cursor = conn.cursor()

    # Create pipeline_runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id TEXT PRIMARY KEY,
        pipeline_name TEXT NOT NULL,
        status TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        execution_mode TEXT NOT NULL,
        max_workers INTEGER,
        total_steps INTEGER DEFAULT 0,
        completed_steps INTEGER DEFAULT 0
    )
    """)

    # Create pipeline_steps table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_steps (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        name TEXT NOT NULL,
        task TEXT NOT NULL,
        status TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        attempt INTEGER NOT NULL DEFAULT 0,
        exit_code INTEGER,
        FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
    )
    """)

    # Create pipeline_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        step_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        log_type TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (step_id) REFERENCES pipeline_steps(id),
        FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
    )
    """)

    # Create scheduled_pipelines table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_pipelines (
        id TEXT PRIMARY KEY,
        pipeline_name TEXT NOT NULL,
        schedule_type TEXT NOT NULL,
        schedule_value TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_run_time TEXT,
        next_run_time TEXT,
        status TEXT NOT NULL
    )
    """)

    # Create pipeline_dependencies table for visualizing step dependencies
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        from_step TEXT NOT NULL,
        to_step TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES pipeline_runs(id),
        FOREIGN KEY (from_step) REFERENCES pipeline_steps(id),
        FOREIGN KEY (to_step) REFERENCES pipeline_steps(id)
    )
    """)

    conn.commit()
    conn.close()


def _check_and_upgrade_schema() -> None:
    """Check and upgrade database schema if needed."""
    if not PipelineConfig.db_path:
        raise RuntimeError('Database path not initialized')

    conn = sqlite3.connect(str(PipelineConfig.db_path))
    cursor = conn.cursor()

    # Check if pipeline_runs has the required columns
    try:
        cursor.execute('SELECT start_time FROM pipeline_runs LIMIT 1')
    except sqlite3.OperationalError:
        # Need to fix the table structure
        # Create pipeline_runs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id TEXT PRIMARY KEY,
            pipeline_name TEXT NOT NULL,
            status TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            execution_mode TEXT NOT NULL,
            max_workers INTEGER,
            total_steps INTEGER DEFAULT 0,
            completed_steps INTEGER DEFAULT 0
        )
        """)

        # Create pipeline_steps table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_steps (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            name TEXT NOT NULL,
            task TEXT NOT NULL,
            status TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            attempt INTEGER NOT NULL DEFAULT 0,
            exit_code INTEGER,
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
        )
        """)

        # Create pipeline_logs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            step_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            log_type TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (step_id) REFERENCES pipeline_steps(id),
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
        )
        """)

        # Create scheduled_pipelines table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_pipelines (
            id TEXT PRIMARY KEY,
            pipeline_name TEXT NOT NULL,
            schedule_type TEXT NOT NULL,
            schedule_value TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_run_time TEXT,
            next_run_time TEXT,
            status TEXT NOT NULL
        )
        """)

        # Create pipeline_dependencies table for visualizing step dependencies
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            from_step TEXT NOT NULL,
            to_step TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(id),
            FOREIGN KEY (from_step) REFERENCES pipeline_steps(id),
            FOREIGN KEY (to_step) REFERENCES pipeline_steps(id)
        )
        """)

    conn.commit()
    conn.close()


def _execute_query(
    query: str, params: tuple[Any, ...] = (), fetch: bool = False
) -> Optional[List[Any]]:
    """
    Execute an SQL query on the database.

    Parameters
    ----------
    query : str
        The SQL query to execute
    params : tuple
        Parameters for the query
    fetch : bool
        Whether to fetch results or not

    Returns
    -------
    Optional[List[Any]]
        Query results if fetch is True, None otherwise
    """
    if not PipelineConfig.db_path:
        raise RuntimeError('Database path not initialized')

    conn = sqlite3.connect(str(PipelineConfig.db_path))
    cursor = conn.cursor()

    try:
        cursor.execute(query, params)

        if fetch:
            result = cursor.fetchall()
        else:
            conn.commit()
            result = None

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    return result


def log_pipeline_start(pipeline_run: PipelineRun) -> None:
    """
    Log the start of a pipeline execution.

    Parameters
    ----------
    pipeline_run : PipelineRun
        The pipeline run to log
    """
    query = """
    INSERT INTO pipeline_runs
    (id, pipeline_name, status, start_time, execution_mode,
     max_workers, total_steps, completed_steps)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        pipeline_run.id,
        pipeline_run.pipeline_name,
        pipeline_run.status,
        pipeline_run.start_time.isoformat(),
        pipeline_run.execution_mode,
        pipeline_run.max_workers,
        len(pipeline_run.steps),
        0,
    )
    _execute_query(query, params)


def log_pipeline_progress(
    pipeline_run: PipelineRun, completed_steps: int
) -> None:
    """
    Log the progress of a pipeline execution.

    Parameters
    ----------
    pipeline_run : PipelineRun
        The pipeline run to log
    completed_steps : int
        Number of completed steps
    """
    query = """
    UPDATE pipeline_runs
    SET completed_steps = ?
    WHERE id = ?
    """
    params = (completed_steps, pipeline_run.id)
    _execute_query(query, params)


def log_pipeline_end(pipeline_run: PipelineRun) -> None:
    """
    Log the end of a pipeline execution.

    Parameters
    ----------
    pipeline_run : PipelineRun
        The pipeline run to log
    """
    query = """
    UPDATE pipeline_runs
    SET status = ?, end_time = ?, completed_steps = ?
    WHERE id = ?
    """

    # Count completed steps
    completed = sum(
        1
        for step in pipeline_run.steps.values()
        if step.status in ['completed', 'skipped']
    )

    params = (
        pipeline_run.status,
        pipeline_run.end_time.isoformat() if pipeline_run.end_time else None,
        completed,
        pipeline_run.id,
    )
    _execute_query(query, params)


def log_step_start(step: PipelineStep, run_id: str) -> None:
    """
    Log the start of a pipeline step.

    Parameters
    ----------
    step : PipelineStep
        The step to log
    run_id : str
        The ID of the pipeline run
    """
    query = """
    INSERT INTO pipeline_steps
    (id, run_id, name, task, status, start_time, attempt)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        step.id,
        run_id,
        step.name,
        step.task,
        step.status,
        step.start_time.isoformat() if step.start_time else None,
        step.attempt,
    )
    _execute_query(query, params)


def log_step_end(step: PipelineStep) -> None:
    """
    Log the end of a pipeline step.

    Parameters
    ----------
    step : PipelineStep
        The step to log
    """
    query = """
    UPDATE pipeline_steps
    SET status = ?, end_time = ?, exit_code = ?, attempt = ?
    WHERE id = ?
    """
    params = (
        step.status,
        step.end_time.isoformat() if step.end_time else None,
        step.exit_code,
        step.attempt,
        step.id,
    )
    _execute_query(query, params)


def log_step_output(
    step_id: str, run_id: str, log_type: str, content: str
) -> int:
    """
    Log the output of a pipeline step.

    Parameters
    ----------
    step_id : str
        The ID of the step
    run_id : str
        The ID of the pipeline run
    log_type : str
        The type of log (stdout or stderr)
    content : str
        The log content

    Returns
    -------
    int
        The ID of the log entry
    """
    query = """
    INSERT INTO pipeline_logs (step_id, run_id, log_type, content, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """
    timestamp = datetime.now().isoformat()
    params = (step_id, run_id, log_type, content, timestamp)
    _execute_query(query, params)

    # Get the log ID
    query = 'SELECT last_insert_rowid()'
    result = _execute_query(query, fetch=True)
    log_id = result[0][0] if result else 0

    # Notify any listeners
    if run_id in PipelineConfig.log_listeners:
        for listener in PipelineConfig.log_listeners[run_id]:
            try:
                listener(
                    {
                        'id': log_id,
                        'step_id': step_id,
                        'run_id': run_id,
                        'log_type': log_type,
                        'content': content,
                        'timestamp': timestamp,
                    }
                )
            except Exception:
                # Ignore errors in listeners to prevent
                # disrupting the main flow
                pass

    return log_id


def log_pipeline_dependencies(
    run_id: str, dependencies: List[Tuple[str, str]]
) -> None:
    """
    Log the dependencies between pipeline steps.

    Parameters
    ----------
    run_id : str
        The ID of the pipeline run
    dependencies : List[Tuple[str, str]]
        List of (from_step, to_step) dependencies
    """
    query = """
    INSERT INTO pipeline_dependencies (run_id, from_step, to_step)
    VALUES (?, ?, ?)
    """

    for from_step, to_step in dependencies:
        params = (run_id, from_step, to_step)
        _execute_query(query, params)


def register_log_listener(run_id: str, listener: Callable[..., Any]) -> None:
    """
    Register a listener for log events.

    Parameters
    ----------
    run_id : str
        The ID of the pipeline run
    listener : Callable
        Function to call when a log event occurs
    """
    if run_id not in PipelineConfig.log_listeners:
        PipelineConfig.log_listeners[run_id] = []

    PipelineConfig.log_listeners[run_id].append(listener)


def unregister_log_listener(run_id: str, listener: Callable[..., Any]) -> None:
    """
    Unregister a listener for log events.

    Parameters
    ----------
    run_id : str
        The ID of the pipeline run
    listener : Callable
        Function to remove from listeners
    """
    if run_id in PipelineConfig.log_listeners:
        if listener in PipelineConfig.log_listeners[run_id]:
            PipelineConfig.log_listeners[run_id].remove(listener)

        if not PipelineConfig.log_listeners[run_id]:
            del PipelineConfig.log_listeners[run_id]


def register_scheduled_pipeline(
    pipeline_name: str,
    schedule_type: str,
    schedule_value: str,
    next_run_time: Optional[datetime] = None,
) -> str:
    """
    Register a scheduled pipeline execution.

    Parameters
    ----------
    pipeline_name : str
        The name of the pipeline
    schedule_type : str
        The type of schedule (cron or interval)
    schedule_value : str
        The schedule value (cron expression or interval in seconds)
    next_run_time : Optional[datetime]
        The next time the pipeline will run

    Returns
    -------
    str
        The ID of the scheduled pipeline
    """
    scheduled_id = f'{pipeline_name}_{int(time.time())}'

    query = """
    INSERT INTO scheduled_pipelines
    (id, pipeline_name, schedule_type, schedule_value,
     created_at, next_run_time, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        scheduled_id,
        pipeline_name,
        schedule_type,
        schedule_value,
        datetime.now().isoformat(),
        next_run_time.isoformat() if next_run_time else None,
        'active',
    )
    _execute_query(query, params)

    return scheduled_id


def update_scheduled_pipeline(
    scheduled_id: str,
    last_run_time: datetime,
    next_run_time: Optional[datetime] = None,
) -> None:
    """
    Update a scheduled pipeline execution.

    Parameters
    ----------
    scheduled_id : str
        The ID of the scheduled pipeline
    last_run_time : datetime
        The last time the pipeline ran
    next_run_time : Optional[datetime]
        The next time the pipeline will run
    """
    query = """
    UPDATE scheduled_pipelines
    SET last_run_time = ?, next_run_time = ?
    WHERE id = ?
    """
    params = (
        last_run_time.isoformat() if last_run_time else None,
        next_run_time.isoformat() if next_run_time else None,
        scheduled_id,
    )
    _execute_query(query, params)


class StreamingSubprocessReader(threading.Thread):
    """
    Thread for reading from subprocess streams in real-time.

    Parameters
    ----------
    stream : io.BufferedReader
        The stream to read from
    callback : Callable[[str], None]
        Function to call with each line of output
    """

    def __init__(self, stream: Any, callback: Callable[[str], None]) -> None:
        """Initialize the reader thread."""
        super().__init__()
        self.stream = stream
        self.callback = callback
        self.daemon = True
        self.stopped = False

    def run(self) -> None:  # Add proper return type annotation
        """Run the reader thread."""
        for line in iter(self.stream.readline, b''):
            if self.stopped:
                break
            decoded_line = line.decode('utf-8')
            self.callback(decoded_line)
        self.stream.close()

    def stop(self) -> None:  # Add proper return type annotation
        """Stop the reader thread."""
        self.stopped = True


class MakimPipeline:
    """
    Handles pipeline execution for Makim.

    Parameters
    ----------
    makim_instance : Makim
        Makim instance containing configuration details.
    """

    def __init__(self, makim_instance: Any):
        """
        Initialize the pipeline handler with configuration.

        Parameters
        ----------
        makim_instance : Makim
            Instance containing configuration details.
        """
        self.makim_instance = makim_instance
        self.config_file = makim_instance.file

        # Initialize global configuration
        init_pipeline_globals(self.config_file)

        # Initialize scheduler for pipeline scheduling
        self._initialize_scheduler()

        # Load existing scheduled pipelines
        self._load_scheduled_pipelines()

    def _initialize_scheduler(self) -> None:
        """Initialize the scheduler for pipeline scheduling."""
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=f'sqlite:///{PipelineConfig.base_dir}/pipeline_scheduler.sqlite'
            )
        }
        self.scheduler = BackgroundScheduler(jobstores=jobstores)
        self.scheduler.start()

    def _load_scheduled_pipelines(self) -> None:
        """Load existing scheduled pipelines from the database."""
        query = """
        SELECT id, pipeline_name, schedule_type, schedule_value, status
        FROM scheduled_pipelines
        WHERE status = 'active'
        """

        scheduled_pipelines = _execute_query(query, fetch=True)

        if not scheduled_pipelines:
            return

        for (
            scheduled_id,
            pipeline_name,
            schedule_type,
            schedule_value,
            status,
        ) in scheduled_pipelines:
            if status != 'active':
                continue

            if schedule_type == 'cron':
                trigger = CronTrigger.from_crontab(schedule_value)
            elif schedule_type == 'interval':
                trigger = IntervalTrigger(seconds=int(schedule_value))
            else:
                continue

            self.scheduler.add_job(
                func=self._run_scheduled_pipeline,
                trigger=trigger,
                args=[scheduled_id, pipeline_name],
                id=scheduled_id,
                replace_existing=True,
            )

    @staticmethod
    def _run_scheduled_pipeline(scheduled_id: str, pipeline_name: str) -> None:
        """Run a scheduled pipeline.

        Parameters
        ----------
        scheduled_id : str
            The ID of the scheduled pipeline
        pipeline_name : str
            The name of the pipeline to run
        """
        # Record execution
        now = datetime.now()
        update_scheduled_pipeline(scheduled_id, now)

        # Run the pipeline
        try:
            # We need to get a fresh instance of makim since we can't
            # serialize it
            from makim.cli.config import extract_root_config
            from makim.core import Makim

            makim = Makim()
            root_config = extract_root_config()
            makim.load(
                file=str(root_config.get('file', '.makim.yaml')),
                verbose=bool(root_config.get('verbose', False)),
            )

            if hasattr(makim, 'pipeline') and makim.pipeline:
                makim.pipeline.run_pipeline(pipeline_name)

            # Update next run time - we can't access scheduler directly due to
            # serialization so we'll need to find it differently
            try:
                conn = sqlite3.connect(
                    str(Path.home() / '.makim' / 'pipeline_scheduler.sqlite')
                )
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT next_run_time FROM apscheduler_jobs WHERE id = ?',
                    (scheduled_id,),
                )
                result = cursor.fetchone()
                next_run_time = (
                    datetime.fromisoformat(result[0])
                    if result and result[0]
                    else None
                )
                conn.close()

                if next_run_time:
                    update_scheduled_pipeline(scheduled_id, now, next_run_time)
            except Exception:
                pass

        except Exception as e:
            print(f'Scheduled pipeline execution failed: {e}')

    def get_pipeline_config(self, pipeline_name: str) -> Dict[str, Any]:
        """
        Get the configuration for a specific pipeline.

        Parameters
        ----------
        pipeline_name : str
            The name of the pipeline.

        Returns
        -------
        Dict[str, Any]
            The pipeline configuration.

        Raises
        ------
        ValueError
            If the pipeline does not exist.
        """
        pipelines = self.makim_instance.global_data.get('pipelines', {})
        if pipeline_name not in pipelines:
            raise ValueError(f"Pipeline '{pipeline_name}' does not exist")
        return cast(Dict[str, Any], pipelines[pipeline_name])

    def get_all_pipelines(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all defined pipelines.

        Returns
        -------
        Dict[str, Dict[str, Any]]
            Dictionary of all pipeline configurations.
        """
        return cast(
            Dict[str, Dict[str, Any]],
            self.makim_instance.global_data.get('pipelines', {}),
        )

    def build_dependency_graph(self, pipeline_name: str) -> nx.DiGraph:
        """
        Build a dependency graph for a pipeline.

        Parameters
        ----------
        pipeline_name : str
            The name of the pipeline.

        Returns
        -------
        nx.DiGraph
            Directed graph representing the pipeline's dependencies.
        """
        pipeline_config = self.get_pipeline_config(pipeline_name)
        steps = pipeline_config.get('steps', [])

        G = nx.DiGraph()

        # Add all steps to the graph
        for i, step in enumerate(steps):
            step_id = step.get('name', f'step_{i}')
            retry_config = step.get('retry', {})

            G.add_node(
                step_id,
                task=step['task'],
                args=step.get('args', {}),
                condition=step.get('condition'),
                retry_config=retry_config,
                timeout=step.get('timeout'),
                step_config=step,
            )

        # Add dependencies
        for i, step in enumerate(steps):
            step_id = step.get('name', f'step_{i}')
            depends_on = step.get('depends_on', [])

            if depends_on:
                # Add explicit dependencies
                for dep in depends_on:
                    G.add_edge(dep, step_id)
            elif i > 0:
                # Add implicit linear dependency if no explicit dependencies
                # are specified
                prev_step_id = steps[i - 1].get('name', f'step_{i - 1}')
                G.add_edge(prev_step_id, step_id)

        # Verify the graph is a DAG (no cycles)
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError(
                f"Pipeline '{pipeline_name}' contains cyclic dependencies"
            )

        return G

    def visualize_pipeline(
        self,
        pipeline_name: str,
        show_status: bool = False,
        run_id: Optional[str] = None,
    ) -> str:
        """Visualize a pipeline as an ASCII graph or text representation.

        Parameters
        ----------
        pipeline_name : str
            The name of the pipeline to visualize
        show_status : bool
            Whether to show status information
        run_id : Optional[str]
            Optional run ID to get status from

        Returns
        -------
        str
            ASCII representation of the pipeline
        """
        try:
            import asciinet
        except ImportError:
            return (
                'To visualize pipelines, install the asciinet package: '
                'pip install asciinet'
            )

        G = self.build_dependency_graph(pipeline_name)
        pipeline_config = self.get_pipeline_config(pipeline_name)

        # Convert to a format asciinet can use
        nodes = list(G.nodes())
        edges = list(G.edges())

        # Get status information if requested
        status_info = {}
        if show_status and run_id:
            query = """
            SELECT name, status
            FROM pipeline_steps
            WHERE run_id = ?
            """
            results = _execute_query(query, (run_id,), fetch=True)

            if results:
                for name, status in results:
                    status_info[name] = status

        # Create display function based on whether to show status
        def make_node_display_with_status(node: str) -> str:
            """Create a node display string with status information."""
            return (
                f'{node}: {G.nodes[node]["task"]} '
                f'[{status_info.get(node, "unknown")}]'
            )

        def make_node_display(node: str) -> str:
            """Create a simple node display string."""
            return f'{node}: {G.nodes[node]["task"]}'

        node_display = (
            make_node_display_with_status
            if show_status and status_info
            else make_node_display
        )

        # Generate ASCII graph
        try:
            ascii_graph = asciinet.graph_to_ascii(
                nodes, edges, node_display=node_display
            )
        except Exception as e:
            # Fallback to a simple text representation if asciinet fails
            ascii_graph = 'Graph visualization failed: ' + str(e)

            # Create simple text representation
            steps_text = []
            for i, node in enumerate(sorted(G.nodes())):
                task = G.nodes[node]['task']
                depends = ', '.join(G.predecessors(node))
                steps_text.append(
                    f'{i + 1}. {node}: {task}'
                    + (f' (depends on: {depends})' if depends else '')
                )

            ascii_graph = '\n'.join(steps_text)

        description = pipeline_config.get('help', 'No description')
        return (
            f'Pipeline: {pipeline_name}\n'
            f'Description: {description}\n\n'
            f'{ascii_graph}'
        )

    def generate_rich_visualization(
        self, pipeline_name: str, run_id: Optional[str] = None
    ) -> Tree:
        """
        Generate a rich Tree visualization of the pipeline.

        Parameters
        ----------
        pipeline_name : str
            The name of the pipeline
        run_id : Optional[str]
            Optional run ID to show status information

        Returns
        -------
        Tree
            Rich Tree object representing the pipeline
        """
        G = self.build_dependency_graph(pipeline_name)
        pipeline_config = self.get_pipeline_config(pipeline_name)

        # Get status information if run_id is provided
        status_info = {}
        if run_id:
            query = """
            SELECT name, status, start_time, end_time
            FROM pipeline_steps
            WHERE run_id = ?
            """
            results = _execute_query(query, (run_id,), fetch=True)

            if results:
                for name, status, start_time, end_time in results:
                    status_info[name] = {
                        'status': status,
                        'start_time': start_time,
                        'end_time': end_time,
                    }

        # Create the root tree
        description = pipeline_config.get('help', 'No description')
        tree = Tree(f'[bold blue]{pipeline_name}[/] - {description}')

        # Find root nodes (no incoming edges)
        root_nodes = [n for n in G.nodes() if G.in_degree(n) == 0]

        # Build tree recursively
        def add_node_to_tree(parent_tree: Tree, node: str) -> None:
            """Add a node and its children to the tree."""
            # Get node information
            task = G.nodes[node]['task']
            condition = G.nodes[node].get('condition')

            # Status styling
            status_style = ''
            status_text = ''
            if node in status_info:
                status = status_info[node]['status']

                if status == 'completed':
                    status_style = 'green'
                elif status == 'failed':
                    status_style = 'red'
                elif status == 'running':
                    status_style = 'yellow'
                elif status == 'skipped':
                    status_style = 'dim'
                else:
                    status_style = 'blue'

                status_text = f' [[{status_style}]{status}[/]]'

                # Add timing information if available
                if (
                    status_info[node]['start_time']
                    and status_info[node]['end_time']
                ):
                    start = datetime.fromisoformat(
                        status_info[node]['start_time']
                    )
                    end = datetime.fromisoformat(status_info[node]['end_time'])
                    duration = (end - start).total_seconds()
                    status_text += f' ({duration:.2f}s)'

            # Create node label
            node_label = f'[cyan]{node}[/]: {task}{status_text}'
            if condition:
                node_label += f'\n  [dim]Condition: {condition}[/]'

            # Add node to tree
            child_tree = parent_tree.add(node_label)

            # Add outgoing edges
            for child in G.successors(node):
                add_node_to_tree(child_tree, child)

        # Add all root nodes
        for root in root_nodes:
            add_node_to_tree(tree, root)

        return tree

    def run_pipeline(
        self,
        pipeline_name: str,
        execution_mode: Optional[str] = None,
        max_workers: Optional[int] = None,
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> bool:
        """
        Execute a pipeline.

        Parameters
        ----------
        pipeline_name : str
            The name of the pipeline to run.
        execution_mode : Optional[str]
            Mode of execution: "sequential" or "parallel"
        max_workers : Optional[int]
            Maximum number of workers for parallel execution
        verbose : bool
            Whether to print verbose output.
        dry_run : bool
            If True, only shows steps without executing them
        debug : bool
            Enable detailed debug logging

        Returns
        -------
        bool
            True if the pipeline executed successfully, False otherwise.
        """
        try:
            # Get pipeline configuration and build dependency graph
            pipeline_config = self.get_pipeline_config(pipeline_name)
            G = self.build_dependency_graph(pipeline_name)

            # Determine execution mode
            if execution_mode is None:
                execution_mode = pipeline_config.get(
                    'default_execution_mode', 'sequential'
                )

            # Determine max workers
            if max_workers is None:
                max_workers = pipeline_config.get('max_workers', 4)

            # Create a run ID and initialize pipeline run
            run_id = f'{pipeline_name}_{int(time.time())}'
            pipeline_run = PipelineRun(
                id=run_id,
                pipeline_name=pipeline_name,
                status='running',
                start_time=datetime.now(),
                execution_mode=execution_mode,
                max_workers=max_workers,
                steps={},
            )

            # Register run in database
            if not dry_run:
                log_pipeline_start(pipeline_run)

                # Log dependencies for visualization
                dependencies = [
                    (source, target) for source, target in G.edges()
                ]
                log_pipeline_dependencies(
                    run_id,
                    [
                        (f'{run_id}_{source}', f'{run_id}_{target}')
                        for source, target in dependencies
                    ],
                )

            # Register running pipeline for potential cancellation
            PipelineConfig.running_pipelines[run_id] = {
                'pipeline_name': pipeline_name,
                'cancel_requested': False,
                'thread_pool': None,
            }

            console = Console()

            # Show the pipeline visualization in debug mode
            if debug:
                console.print('\n[bold cyan]Pipeline Structure:[/]')
                tree = self.generate_rich_visualization(pipeline_name)
                console.print(tree)
                console.print()

            console.print(
                f'[bold green]Running pipeline:[/] '
                f'[bold blue]{pipeline_name}[/] '
                f'[yellow](mode: {execution_mode})[/]'
            )

            if dry_run:
                console.print(
                    '[bold yellow]DRY RUN MODE - No steps will be executed[/]'
                )

            if debug:
                console.print(
                    '[bold cyan]DEBUG MODE - '
                    'Detailed logs will be displayed[/]'
                )

            # Prepare steps from the graph
            step_list = []
            for node_id in G.nodes():
                node = G.nodes[node_id]
                step = PipelineStep(
                    id=f'{run_id}_{node_id}',
                    name=node_id,
                    task=node['task'],
                    args=node.get('args', {}),
                    condition=node.get('condition'),
                    depends_on=[pred for pred in G.predecessors(node_id)],
                    retry_config=node.get('retry_config', {}),
                    timeout=node.get('timeout'),
                    status='pending',
                )
                pipeline_run.steps[node_id] = step
                step_list.append(step)

            # Run the pipeline based on execution mode
            success = False
            if execution_mode == 'sequential':
                success = self._run_pipeline_sequential(
                    pipeline_run,
                    G,
                    verbose=verbose,
                    dry_run=dry_run,
                    debug=debug,
                )
            else:  # parallel
                success = self._run_pipeline_parallel(
                    pipeline_run,
                    G,
                    max_workers=max_workers,
                    verbose=verbose,
                    dry_run=dry_run,
                    debug=debug,
                )

            # Update pipeline status and completion time
            pipeline_run.end_time = datetime.now()
            pipeline_run.status = 'completed' if success else 'failed'

            if not dry_run:
                log_pipeline_end(pipeline_run)

            # Clean up running pipeline record
            if run_id in PipelineConfig.running_pipelines:
                del PipelineConfig.running_pipelines[run_id]

            # Show final status with timing info
            duration = (
                pipeline_run.end_time - pipeline_run.start_time
            ).total_seconds()

            if success:
                console.print(
                    f'[bold green]Pipeline completed successfully:[/] '
                    f'[bold blue]{pipeline_name}[/]'
                )
            else:
                console.print(
                    f'[bold red]Pipeline failed:[/] '
                    f'[bold blue]{pipeline_name}[/]'
                )

            console.print(f'[yellow]Total time:[/] {duration:.2f} seconds')

            # Show a summary of step statuses in verbose mode
            if verbose or debug:
                status_table = Table(title='Step Summary', box=box.ROUNDED)
                status_table.add_column('Step', style='cyan')
                status_table.add_column('Task', style='blue')
                status_table.add_column('Status', style='yellow')
                status_table.add_column('Duration', style='green')

                for step_id, step in pipeline_run.steps.items():
                    step_duration = 'N/A'
                    if step.start_time and step.end_time:
                        secs = (
                            step.end_time - step.start_time
                        ).total_seconds()
                        step_duration = f'{secs:.2f}s'

                    status = step.status
                    status_style = ''
                    if status == 'completed':
                        status_style = 'green'
                    elif status == 'failed':
                        status_style = 'red'
                    elif status == 'running':
                        status_style = 'yellow'
                    elif status == 'skipped':
                        status_style = 'dim'

                    status_table.add_row(
                        step_id,
                        step.task,
                        f'[{status_style}]{status}[/]',
                        step_duration,
                    )

                console.print(status_table)

            return success

        except ValueError as e:
            console = Console()
            console.print(f'[bold red]Pipeline configuration error:[/] {e!s}')
            return False
        except Exception as e:
            console = Console()
            console.print(f'[bold red]Pipeline execution failed:[/] {e!s}')
            return False

    def _run_pipeline_sequential(
        self,
        pipeline_run: PipelineRun,
        G: nx.DiGraph,
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> bool:
        """
        Run a pipeline in sequential mode.

        Parameters
        ----------
        pipeline_run : PipelineRun
            The pipeline run context
        G : nx.DiGraph
            The dependency graph
        verbose : bool
            Whether to print verbose output
        dry_run : bool
            If True, only shows steps without executing them
        debug : bool
            Enable detailed debug logging

        Returns
        -------
        bool
            True if all steps completed successfully, False otherwise
        """
        console = Console()
        run_id = pipeline_run.id

        # Get topological sort order
        try:
            execution_order = list(nx.topological_sort(G))
        except nx.NetworkXUnfeasible:
            console.print(
                '[bold red]Error:[/] Pipeline has cyclic dependencies'
            )
            return False

        if verbose or debug:
            console.print('[bold]Execution order:[/]')
            for i, step_id in enumerate(execution_order):
                task_name = G.nodes[step_id]['task']
                console.print(f'  {i + 1}. [cyan]{step_id}[/]: {task_name}')

        # Set up progress tracking with enhanced columns
        with Progress(
            SpinnerColumn(),
            TextColumn('[progress.description]{task.description}'),
            BarColumn(),
            TextColumn('[progress.percentage]{task.percentage:>3.0f}%'),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            disable=dry_run,
        ) as progress:
            # Create overall pipeline progress task
            pipeline_task = progress.add_task(
                f'[green]Pipeline: {pipeline_run.pipeline_name}',
                total=len(execution_order),
            )

            # Execute steps in order
            all_succeeded = True
            completed_steps: Set[str] = set()

            for step_id in execution_order:
                step = pipeline_run.steps[step_id]

                # Check if cancellation was requested
                if (
                    run_id in PipelineConfig.running_pipelines
                    and PipelineConfig.running_pipelines[run_id][
                        'cancel_requested'
                    ]
                ):
                    console.print('[bold yellow]Pipeline cancelled by user[/]')
                    pipeline_run.status = 'cancelled'
                    return False

                # Check dependencies
                dependencies_met = True
                for dep_id in step.depends_on:
                    if dep_id not in completed_steps:
                        dependencies_met = False
                        break

                if not dependencies_met:
                    console.print(
                        f'[yellow]Skipping step[/] [cyan]{step_id}[/] - '
                        f'dependencies not met'
                    )
                    step.status = 'skipped'
                    if not dry_run:
                        step.end_time = datetime.now()
                        log_step_end(step)
                    completed_steps.add(step_id)
                    progress.update(pipeline_task, advance=1)
                    continue

                # Create step task
                step_task = progress.add_task(
                    f'[cyan]{step_id}[/]: {step.task}',
                    total=1,
                    visible=not dry_run,
                )

                # Execute the step
                success = self._execute_step(
                    step,
                    pipeline_run,
                    progress,
                    step_task=step_task,
                    verbose=verbose,
                    dry_run=dry_run,
                    debug=debug,
                )

                if success or dry_run:
                    completed_steps.add(step_id)

                # Update pipeline progress
                progress.update(pipeline_task, advance=1)

                # Update database with progress
                if not dry_run:
                    log_pipeline_progress(pipeline_run, len(completed_steps))

                if not success and not dry_run:
                    all_succeeded = False
                    break

            return all_succeeded or dry_run

    def _run_pipeline_parallel(
        self,
        pipeline_run: PipelineRun,
        G: nx.DiGraph,
        max_workers: int = 4,
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> bool:
        """
        Run a pipeline in parallel mode.

        Parameters
        ----------
        pipeline_run : PipelineRun
            The pipeline run context
        G : nx.DiGraph
            The dependency graph
        max_workers : int
            Maximum number of concurrent workers
        verbose : bool
            Whether to print verbose output
        dry_run : bool
            If True, only shows steps without executing them
        debug : bool
            Enable detailed debug logging

        Returns
        -------
        bool
            True if all steps completed successfully, False otherwise
        """
        console = Console()
        run_id = pipeline_run.id

        # Check for valid graph
        if not nx.is_directed_acyclic_graph(G):
            console.print(
                '[bold red]Error:[/] Pipeline has cyclic dependencies'
            )
            return False

        # Set up progress tracking with enhanced columns
        with Progress(
            SpinnerColumn(),
            TextColumn('[progress.description]{task.description}'),
            BarColumn(),
            TextColumn('[progress.percentage]{task.percentage:>3.0f}%'),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            disable=dry_run,
        ) as progress:
            # Create overall pipeline progress task
            pipeline_task = progress.add_task(
                f'[green]Pipeline: {pipeline_run.pipeline_name}',
                total=len(G.nodes()),
            )

            # Prepare for parallel execution
            completed_steps: Set[str] = set()
            pending_steps: Set[str] = set(G.nodes())
            failed_steps: Set[str] = set()
            step_progress: Dict[str, TaskID] = {}

            # Create thread pool
            executor = ThreadPoolExecutor(max_workers=max_workers)
            PipelineConfig.running_pipelines[run_id]['thread_pool'] = executor

            try:
                # Execute steps in parallel respecting dependencies
                while pending_steps and not failed_steps:
                    # Check if cancellation was requested
                    if (
                        run_id in PipelineConfig.running_pipelines
                        and PipelineConfig.running_pipelines[run_id][
                            'cancel_requested'
                        ]
                    ):
                        console.print(
                            '[bold yellow]Pipeline cancelled by user[/]'
                        )
                        pipeline_run.status = 'cancelled'
                        return False

                    # Find steps that are ready to execute
                    ready_steps = []
                    for step_id in pending_steps:
                        # Check if all dependencies are satisfied
                        deps = set(G.predecessors(step_id))
                        if deps.issubset(completed_steps):
                            ready_steps.append(step_id)

                    if not ready_steps:
                        if pending_steps:
                            # Deadlock detected - can happen if there's an
                            # error in dependency graph
                            console.print(
                                '[bold red]Error:[/] Deadlock detected in '
                                'pipeline execution'
                            )
                            return False
                        break

                    # Execute ready steps in parallel
                    futures = {}
                    for step_id in ready_steps:
                        step = pipeline_run.steps[step_id]

                        # Create progress bar for this step
                        step_task = progress.add_task(
                            f'[cyan]{step_id}[/]: {step.task}',
                            total=1,
                            visible=not dry_run,
                        )
                        step_progress[step_id] = step_task

                        pending_steps.remove(step_id)

                        if dry_run:
                            console.print(
                                f'[yellow]Would execute step[/] '
                                f'[cyan]{step_id}[/]: {step.task}'
                            )
                            completed_steps.add(step_id)
                            progress.update(step_task, advance=1)
                            progress.update(pipeline_task, advance=1)
                            continue

                        # Submit step for execution
                        future = executor.submit(
                            self._execute_step,
                            step,
                            pipeline_run,
                            progress,
                            step_task,
                            verbose,
                            dry_run,
                            debug,
                        )
                        futures[future] = step_id

                    # Wait for at least one step to complete
                    if futures:
                        done, _ = concurrent.futures.wait(
                            futures.keys(),
                            return_when=concurrent.futures.FIRST_COMPLETED,
                        )

                        for future in done:
                            step_id = futures[future]

                            try:
                                success = future.result()
                                if success:
                                    completed_steps.add(step_id)
                                    progress.update(pipeline_task, advance=1)
                                    # Update database with progress
                                    log_pipeline_progress(
                                        pipeline_run, len(completed_steps)
                                    )
                                else:
                                    failed_steps.add(step_id)
                            except Exception as e:
                                console.print(
                                    f'[bold red]Step execution failed:[/] '
                                    f'{step_id} - {e!s}'
                                )
                                failed_steps.add(step_id)

                if dry_run:
                    return True

                # Final progress update
                log_pipeline_progress(pipeline_run, len(completed_steps))

                return len(failed_steps) == 0

            finally:
                # Ensure executor is shutdown
                executor.shutdown(wait=False, cancel_futures=True)

    def _execute_step(
        self,
        step: PipelineStep,
        pipeline_run: PipelineRun,
        progress: Optional[Progress] = None,
        step_task: Optional[TaskID] = None,
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> bool:
        """
        Execute a single pipeline step.

        Parameters
        ----------
        step : PipelineStep
            The step to execute
        pipeline_run : PipelineRun
            The pipeline run context
        progress : Optional[Progress]
            Progress tracking object
        step_task : Optional[TaskID]
            Task ID for this step in the progress tracker
        verbose : bool
            Whether to print verbose output
        dry_run : bool
            If True, only shows steps without executing them
        debug : bool
            Enable detailed debug logging

        Returns
        -------
        bool
            True if the step completed successfully, False otherwise
        """
        console = Console()

        if dry_run:
            console.print(
                f'[yellow]Would execute step[/] '
                f'[cyan]{step.name}[/]: {step.task}'
            )
            return True

        # Update step status
        step.status = 'running'
        step.start_time = datetime.now()
        step.attempt += 1

        # Log step start
        if not dry_run:
            log_step_start(step, pipeline_run.id)

        if debug or verbose:
            console.print(
                f'[bold]Starting step[/] [cyan]{step.name}[/]: {step.task}'
            )

        # Check condition if present
        if step.condition:
            # Simple condition evaluation (can be expanded)
            try:
                if not eval(step.condition):  # nosec B307
                    if debug or verbose:
                        console.print(
                            f'[yellow]Skipping step[/] [cyan]{step.name}[/] - '
                            f'condition not met: {step.condition}'
                        )

                    step.status = 'skipped'
                    step.end_time = datetime.now()

                    if not dry_run:
                        log_step_end(step)

                    if progress and step_task:
                        progress.update(step_task, advance=1)

                    return True
            except Exception as e:
                console.print(
                    f'[bold red]Error evaluating condition[/] for step '
                    f'[cyan]{step.name}[/]: {e}'
                )

                step.status = 'failed'
                step.end_time = datetime.now()
                step.stderr = f'Error evaluating condition: {e!s}'
                step.exit_code = 1

                if not dry_run:
                    log_step_end(step)
                    log_step_output(
                        step.id, pipeline_run.id, 'stderr', step.stderr or ''
                    )

                if progress and step_task:
                    progress.update(step_task, advance=1)

                return False

        # Prepare command
        cmd = ['makim', '--file', self.config_file, step.task]

        # Add arguments
        for key, value in step.args.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f'--{key}')
            else:
                cmd.extend([f'--{key}', str(value)])

        # Log command
        cmd_str = ' '.join(shlex.quote(str(arg)) for arg in cmd)

        if debug:
            console.print(f'[yellow]Executing command:[/] {cmd_str}')

        # Execute with retries if configured
        max_attempts = (
            step.retry_config.get('attempts', 1) if step.retry_config else 1
        )
        backoff = (
            step.retry_config.get('backoff', 0) if step.retry_config else 0
        )

        for attempt in range(max_attempts):
            if attempt > 0:
                if debug or verbose:
                    console.print(
                        f'[yellow]Retrying step[/] [cyan]{step.name}[/] - '
                        f'attempt {attempt + 1}/{max_attempts}'
                    )

                # Wait before retry
                time.sleep(backoff)

            try:
                # If debugging or following logs, use streaming output
                if debug or 'follow' in pipeline_run.id:
                    result = self._execute_with_live_output(
                        cmd,
                        step,
                        pipeline_run.id,
                        progress,
                        step_task,
                        timeout=step.timeout,
                    )
                else:
                    # Execute command with timeout if specified
                    cmd_result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=step.timeout,
                    )
                    result = {'exit_code': cmd_result.returncode}

                    # Update progress incrementally for long-running tasks
                    if progress and step_task:
                        for i in range(10):
                            progress.update(step_task, completed=i / 10)
                            time.sleep(0.01)

                # Update step information
                step.status = 'completed'
                step.end_time = datetime.now()

                if not isinstance(result, dict):  # Regular subprocess result
                    step.stdout = result.stdout
                    step.stderr = result.stderr
                    step.exit_code = 0

                    # Log output
                    if not dry_run:
                        log_step_end(step)
                        log_step_output(
                            step.id, pipeline_run.id, 'stdout', result.stdout
                        )
                        log_step_output(
                            step.id, pipeline_run.id, 'stderr', result.stderr
                        )
                else:
                    # Live output was already logged
                    step.exit_code = 0
                    if not dry_run:
                        log_step_end(step)

                if debug and not isinstance(result, dict):
                    console.print(
                        f'[green]Step completed:[/] [cyan]{step.name}[/]'
                    )
                    console.print('[yellow]STDOUT:[/]')
                    console.print(result.stdout)
                    if result.stderr:
                        console.print('[yellow]STDERR:[/]')
                        console.print(result.stderr)

                if progress and step_task:
                    progress.update(step_task, completed=1.0)

                return True

            except subprocess.TimeoutExpired as e:
                error_msg = f'Step timed out after {step.timeout} seconds'
                # Convert bytes to str safely for stderr
                stderr = (
                    e.stderr.decode('utf-8')
                    if isinstance(e.stderr, bytes)
                    else (e.stderr or '')
                )
                stdout = (
                    e.stdout.decode('utf-8')
                    if isinstance(e.stdout, bytes)
                    else (e.stdout or '')
                )

                step.stderr = f'{error_msg}\n{stderr}'
                step.stdout = stdout
                step.exit_code = 124  # Standard timeout exit code

                if not dry_run:
                    log_step_output(
                        step.id, pipeline_run.id, 'stdout', step.stdout
                    )
                    log_step_output(
                        step.id, pipeline_run.id, 'stderr', step.stderr
                    )

                if debug or verbose:
                    console.print(
                        f'[bold red]Step timeout:[/] [cyan]{step.name}[/] - '
                        f'{error_msg}'
                    )

                # Continue to next retry if available
                if attempt == max_attempts - 1:
                    step.status = 'failed'
                    step.end_time = datetime.now()

                    if not dry_run:
                        log_step_end(step)

                    if progress and step_task:
                        progress.update(step_task, completed=1.0)

                    return False

            except subprocess.CalledProcessError as e:
                error_msg = f'Step failed with exit code {e.returncode}'
                step.stderr = f'{error_msg}\n{e.stderr or ""}'
                step.stdout = e.stdout or ''
                step.exit_code = e.returncode

                if not dry_run:
                    log_step_output(
                        step.id, pipeline_run.id, 'stdout', step.stdout
                    )
                    log_step_output(
                        step.id, pipeline_run.id, 'stderr', step.stderr
                    )

                if debug or verbose:
                    console.print(
                        f'[bold red]Step failed:[/] [cyan]{step.name}[/] - '
                        f'{error_msg}'
                    )
                    console.print('[yellow]STDERR:[/]')
                    console.print(e.stderr)

                # Continue to next retry if available
                if attempt == max_attempts - 1:
                    step.status = 'failed'
                    step.end_time = datetime.now()

                    if not dry_run:
                        log_step_end(step)

                    if progress and step_task:
                        progress.update(step_task, completed=1.0)

                    return False

            except Exception as e:
                error_msg = f'Unexpected error: {e!s}'
                step.stderr = error_msg
                step.exit_code = 1

                if not dry_run:
                    log_step_output(
                        step.id, pipeline_run.id, 'stderr', step.stderr
                    )

                if debug or verbose:
                    console.print(
                        f'[bold red]Step error:[/] [cyan]{step.name}[/] - '
                        f'{error_msg}'
                    )

                # Continue to next retry if available
                if attempt == max_attempts - 1:
                    step.status = 'failed'
                    step.end_time = datetime.now()

                    if not dry_run:
                        log_step_end(step)

                    if progress and step_task:
                        progress.update(step_task, completed=1.0)

                    return False

        # This should never be reached, but just in case
        return False

    def _execute_with_live_output(
        self,
        cmd: List[str],
        step: PipelineStep,
        run_id: str,
        progress: Optional[Progress] = None,
        step_task: Optional[TaskID] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute a command with real-time output streaming.

        Parameters
        ----------
        cmd : List[str]
            Command to execute
        step : PipelineStep
            Step being executed
        run_id : str
            Pipeline run ID
        progress : Optional[Progress]
            Progress tracking object
        step_task : Optional[TaskID]
            Task ID for this step
        timeout : Optional[int]
            Timeout in seconds

        Returns
        -------
        Dict[str, Any]
            Result information
        """
        process = None
        stdout_reader = None
        stderr_reader = None

        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )

            # Set up output handlers
            def handle_stdout(line: str) -> None:
                """Handle stdout line from subprocess."""
                log_step_output(step.id, run_id, 'stdout', line.rstrip())
                if progress and step_task:
                    # Update progress incrementally
                    current = progress.tasks[step_task].completed
                    if current < MAX_PROGRESS:  # Leave room for completion
                        progress.update(
                            step_task,
                            completed=min(
                                current + PROGRESS_INCREMENT, MAX_PROGRESS
                            ),
                        )

            def handle_stderr(line: str) -> None:
                """Handle stderr line from subprocess."""
                log_step_output(step.id, run_id, 'stderr', line.rstrip())

            # Start output readers
            stdout_reader = StreamingSubprocessReader(
                process.stdout, handle_stdout
            )
            stderr_reader = StreamingSubprocessReader(
                process.stderr, handle_stderr
            )

            stdout_reader.start()
            stderr_reader.start()

            # Wait for process with timeout
            start_time = time.time()
            while True:
                # Check if process has finished
                if process.poll() is not None:
                    break

                # Check for timeout
                if timeout and time.time() - start_time > timeout:
                    process.terminate()
                    time.sleep(0.5)
                    if process.poll() is None:
                        process.kill()
                    raise subprocess.TimeoutExpired(cmd, timeout or 0)

                # Sleep briefly to avoid CPU spin
                time.sleep(0.1)

            # Process completed
            exit_code = process.poll()
            if exit_code != 0:
                raise subprocess.CalledProcessError(exit_code or 1, cmd)

            return {'exit_code': 0}

        finally:
            # Clean up readers
            if stdout_reader:
                stdout_reader.stop()
            if stderr_reader:
                stderr_reader.stop()

            # Ensure process is terminated
            if process and process.poll() is None:
                process.terminate()
                time.sleep(0.5)
                if process.poll() is None:
                    process.kill()

    def schedule_pipeline(
        self,
        pipeline_name: str,
        cron: Optional[str] = None,
        interval: Optional[int] = None,
    ) -> bool:
        """
        Schedule a pipeline to run automatically.

        Parameters
        ----------
        pipeline_name : str
            The name of the pipeline to schedule
        cron : Optional[str]
            Cron expression for scheduling
        interval : Optional[int]
            Interval in seconds between executions

        Returns
        -------
        bool
            True if scheduling succeeded, False otherwise
        """
        try:
            # Validate pipeline exists
            self.get_pipeline_config(pipeline_name)

            if not cron and not interval:
                raise ValueError('Either cron or interval must be specified')

            if cron and interval:
                raise ValueError(
                    'Only one of cron or interval can be specified'
                )

            # Create trigger
            if cron:
                trigger = CronTrigger.from_crontab(cron)
                schedule_type = 'cron'
                schedule_value = cron
            else:
                if interval is None:
                    raise ValueError(
                        'Interval must not be None for interval scheduling'
                    )
                trigger = IntervalTrigger(seconds=interval)
                schedule_type = 'interval'
                schedule_value = str(interval)

            # Register in database
            scheduled_id = register_scheduled_pipeline(
                pipeline_name,
                schedule_type,
                schedule_value,
                trigger.get_next_fire_time(None, datetime.now()),
            )

            # Register with scheduler
            self.scheduler.add_job(
                func=self._run_scheduled_pipeline,
                trigger=trigger,
                args=[scheduled_id, pipeline_name],
                id=scheduled_id,
                replace_existing=True,
            )

            return True

        except Exception as e:
            console = Console()
            console.print(f'[bold red]Failed to schedule pipeline:[/] {e!s}')
            return False

    def unschedule_pipeline(self, scheduled_id_or_name: str) -> bool:
        """
        Remove a scheduled pipeline.

        Parameters
        ----------
        scheduled_id_or_name : str
            The ID or name of the scheduled pipeline

        Returns
        -------
        bool
            True if unscheduling succeeded, False otherwise
        """
        try:
            # Check if the input is a scheduled ID or pipeline name
            query = """
            SELECT id FROM scheduled_pipelines
            WHERE id = ? OR pipeline_name = ?
            AND status = 'active'
            """

            result = _execute_query(
                query, (scheduled_id_or_name, scheduled_id_or_name), fetch=True
            )

            if not result:
                raise ValueError(
                    f"No active schedule found for '{scheduled_id_or_name}'"
                )

            scheduled_id = result[0][0]

            # Update status in database
            query = """
            UPDATE scheduled_pipelines
            SET status = 'inactive'
            WHERE id = ?
            """

            _execute_query(query, (scheduled_id,))

            # Remove from scheduler
            self.scheduler.remove_job(scheduled_id)

            return True

        except Exception as e:
            console = Console()
            console.print(f'[bold red]Failed to unschedule pipeline:[/] {e!s}')
            return False

    def get_scheduled_pipelines(self) -> List[Dict[str, Any]]:
        """
        Get all scheduled pipelines.

        Returns
        -------
        List[Dict[str, Any]]
            List of scheduled pipelines
        """
        query = """
        SELECT id, pipeline_name, schedule_type, schedule_value,
               created_at, last_run_time, next_run_time, status
        FROM scheduled_pipelines
        WHERE status = 'active'
        """

        results = _execute_query(query, fetch=True)

        if not results:
            return []

        scheduled = []
        for row in results:
            scheduled.append(
                {
                    'id': row[0],
                    'pipeline_name': row[1],
                    'schedule_type': row[2],
                    'schedule_value': row[3],
                    'created_at': row[4],
                    'last_run_time': row[5],
                    'next_run_time': row[6],
                    'status': row[7],
                }
            )

        return scheduled

    def get_pipeline_history(
        self,
        pipeline_name: Optional[str] = None,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get pipeline execution history.

        Parameters
        ----------
        pipeline_name : Optional[str]
            Optional filter by pipeline name
        limit : int
            Maximum number of records to return
        status : Optional[str]
            Optional filter by status (running, completed, failed, cancelled)

        Returns
        -------
        List[Dict[str, Any]]
            List of pipeline execution records
        """
        query_parts = [
            """
            SELECT id, pipeline_name, status, start_time, end_time,
                   execution_mode, total_steps, completed_steps
            FROM pipeline_runs
            """
        ]
        params = []

        where_clauses = []

        if pipeline_name:
            where_clauses.append('pipeline_name = ?')
            params.append(pipeline_name)

        if status:
            where_clauses.append('status = ?')
            params.append(status)

        if where_clauses:
            query_parts.append('WHERE ' + ' AND '.join(where_clauses))

        query_parts.append('ORDER BY start_time DESC')

        if limit:
            query_parts.append('LIMIT ?')
            params.append(str(limit))

        query = ' '.join(query_parts)

        results = _execute_query(query, tuple(params), fetch=True)

        if not results:
            return []

        history = []
        for row in results:
            run_id = row[0]

            # Get step information
            steps_query = """
            SELECT name, task, status, start_time, end_time, exit_code
            FROM pipeline_steps
            WHERE run_id = ?
            """

            steps_results = _execute_query(steps_query, (run_id,), fetch=True)
            steps = []

            if steps_results:
                for step_row in steps_results:
                    steps.append(
                        {
                            'name': step_row[0],
                            'task': step_row[1],
                            'status': step_row[2],
                            'start_time': step_row[3],
                            'end_time': step_row[4],
                            'exit_code': step_row[5],
                        }
                    )

            total_steps = row[6] or len(steps)
            completed_steps = row[7] or sum(
                1 for s in steps if s['status'] in ['completed', 'skipped']
            )
            progress = (
                (completed_steps / total_steps) * 100 if total_steps > 0 else 0
            )

            history.append(
                {
                    'id': run_id,
                    'pipeline_name': row[1],
                    'status': row[2],
                    'start_time': row[3],
                    'end_time': row[4],
                    'execution_mode': row[5],
                    'total_steps': total_steps,
                    'completed_steps': completed_steps,
                    'progress': progress,
                    'steps': steps,
                }
            )

        return history

    def follow_pipeline_logs(
        self,
        run_id: Optional[str] = None,
        pipeline_name: Optional[str] = None,
        callback: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        Follow logs for a pipeline in real-time.

        Parameters
        ----------
        run_id : Optional[str]
            The run ID to follow
        pipeline_name : Optional[str]
            The pipeline name to follow (will use most recent run)
        callback : Optional[Callable]
            Function to call with each new log entry
        """
        # If pipeline name is provided but not run_id, get the most recent run
        if pipeline_name and not run_id:
            query = """
            SELECT id FROM pipeline_runs
            WHERE pipeline_name = ?
            ORDER BY start_time DESC
            LIMIT 1
            """

            result = _execute_query(query, (pipeline_name,), fetch=True)

            if not result:
                raise ValueError(
                    f"No runs found for pipeline '{pipeline_name}'"
                )

            run_id = result[0][0]

        if not run_id:
            raise ValueError('Either run_id or pipeline_name must be provided')

        # Register callback for new logs
        if callback:
            register_log_listener(run_id, callback)

    def get_pipeline_logs(
        self,
        run_id: Optional[str] = None,
        pipeline_name: Optional[str] = None,
        step_name: Optional[str] = None,
        limit: int = 100,
        log_type: Optional[str] = None,
        since_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get logs for pipeline executions.

        Parameters
        ----------
        run_id : Optional[str]
            Optional filter by run ID
        pipeline_name : Optional[str]
            Optional filter by pipeline name
        step_name : Optional[str]
            Optional filter by step name
        limit : int
            Maximum number of records to return
        log_type : Optional[str]
            Optional filter by log type (stdout or stderr)
        since_id : int
            Only return logs with ID greater than this

        Returns
        -------
        List[Dict[str, Any]]
            List of log records
        """
        # If pipeline name is provided but not run_id, get the most recent run
        if pipeline_name and not run_id:
            query = """
            SELECT id FROM pipeline_runs
            WHERE pipeline_name = ?
            ORDER BY start_time DESC
            LIMIT 1
            """

            result = _execute_query(query, (pipeline_name,), fetch=True)

            if result:
                run_id = result[0][0]

        # Start with base query that joins tables to get relevant information
        query_parts = [
            """
            SELECT pl.id, pl.run_id, pr.pipeline_name, ps.name, pl.log_type,
                   pl.content, pl.timestamp
            FROM pipeline_logs pl
            JOIN pipeline_runs pr ON pl.run_id = pr.id
            JOIN pipeline_steps ps ON pl.step_id = ps.id
            """
        ]
        params = []

        where_clauses = []

        if run_id:
            where_clauses.append('pl.run_id = ?')
            params.append(run_id)

        if pipeline_name and not run_id:
            where_clauses.append('pr.pipeline_name = ?')
            params.append(pipeline_name)

        if step_name:
            where_clauses.append('ps.name = ?')
            params.append(step_name)

        if log_type:
            where_clauses.append('pl.log_type = ?')
            params.append(log_type)

        if since_id > 0:
            where_clauses.append('pl.id > ?')
            params.append(str(since_id))

        if where_clauses:
            query_parts.append('WHERE ' + ' AND '.join(where_clauses))

        query_parts.append('ORDER BY pl.timestamp ASC')

        if limit:
            query_parts.append('LIMIT ?')
            params.append(str(limit))

        query = ' '.join(query_parts)

        results = _execute_query(query, tuple(params), fetch=True)

        if not results:
            return []

        logs = []
        for row in results:
            logs.append(
                {
                    'id': row[0],
                    'run_id': row[1],
                    'pipeline_name': row[2],
                    'step_name': row[3],
                    'log_type': row[4],
                    'content': row[5],
                    'timestamp': row[6],
                }
            )

        return logs

    def clear_logs(self) -> bool:
        """
        Clear all pipeline logs.

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        try:
            _execute_query('DELETE FROM pipeline_logs')
            return True
        except Exception as e:
            console = Console()
            console.print(f'[bold red]Failed to clear logs:[/] {e!s}')
            return False

    def cancel_pipeline(self, run_id_or_name: str) -> bool:
        """
        Cancel a running pipeline.

        Parameters
        ----------
        run_id_or_name : str
            The ID or name of the running pipeline

        Returns
        -------
        bool
            True if cancellation was requested, False otherwise
        """
        # Find the pipeline run
        for run_id, pipeline_info in PipelineConfig.running_pipelines.items():
            if (
                run_id == run_id_or_name
                or pipeline_info['pipeline_name'] == run_id_or_name
            ):
                # Mark for cancellation
                PipelineConfig.running_pipelines[run_id][
                    'cancel_requested'
                ] = True

                # If there's a thread pool, try to shut it down
                thread_pool = PipelineConfig.running_pipelines[run_id].get(
                    'thread_pool'
                )
                if thread_pool:
                    thread_pool.shutdown(wait=False, cancel_futures=True)

                return True

        console = Console()
        console.print(
            f'[yellow]No running pipeline found with ID or name:[/] '
            f'{run_id_or_name}'
        )
        return False

    def retry_failed_pipeline(
        self, pipeline_name: str, all_steps: bool = False
    ) -> bool:
        """
        Retry a failed pipeline.

        Parameters
        ----------
        pipeline_name : str
            The name of the failed pipeline to retry
        all_steps : bool
            If True, retry all steps, otherwise only failed steps

        Returns
        -------
        bool
            True if retry was successful, False otherwise
        """
        try:
            # Find the most recent failed execution
            query = """
            SELECT id FROM pipeline_runs
            WHERE pipeline_name = ? AND status = 'failed'
            ORDER BY start_time DESC
            LIMIT 1
            """

            result = _execute_query(query, (pipeline_name,), fetch=True)

            if not result:
                raise ValueError(
                    f"No failed execution found for pipeline '{pipeline_name}'"
                )

            run_id = result[0][0]

            # If retrying all steps, just run the pipeline again
            if all_steps:
                return self.run_pipeline(pipeline_name)

            # Find failed steps
            query = """
            SELECT name, task FROM pipeline_steps
            WHERE run_id = ? AND status = 'failed'
            """

            failed_steps = _execute_query(query, (run_id,), fetch=True)

            if not failed_steps:
                raise ValueError('No failed steps found to retry')

            console = Console()
            console.print(
                f'[bold blue]Retrying failed steps for pipeline:[/] '
                f'{pipeline_name}'
            )

            # Execute each failed step
            success = True
            for step_name, task in failed_steps:
                console.print(
                    f'[yellow]Retrying step:[/] {step_name} ({task})'
                )

                # Execute the task
                cmd = ['makim', '--file', self.config_file, task]

                try:
                    subprocess.run(
                        cmd, capture_output=True, text=True, check=True
                    )
                    console.print(
                        f'[green]Step retry successful:[/] {step_name}'
                    )
                except subprocess.CalledProcessError as e:
                    console.print(
                        f'[bold red]Step retry failed:[/] {step_name}'
                    )
                    console.print(f'[red]Error:[/] {e.stderr}')
                    success = False

            return success

        except Exception as e:
            console = Console()
            console.print(f'[bold red]Failed to retry pipeline:[/] {e!s}')
            return False
