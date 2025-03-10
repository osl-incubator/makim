import concurrent.futures
from collections import deque
import makim.core
from makim.logs import MakimLogs, MakimError


class PipelineExecutor:
    """Handles execution of pipelines, supporting retries and error recovery."""

    def __init__(self, makim_instance=None, debug=False):
        self.makim = makim_instance if makim_instance else get_makim_instance()
        self.task_state = {}  # Track execution state
        self.debug = debug
        self.task_attempts = {}  # Track task retry attempts
        self.failed_tasks = {}  # Store failed tasks with error messages
        self.debug = debug

    def read_pipeline(self, pipeline_name: str):
        """Fetches the pipeline configuration from .makim.yaml."""
        if "pipelines" not in self.makim.global_data:
            MakimLogs.raise_error(f"No pipelines found in configuration.", MakimError.MAKIM_CONFIG_FILE_INVALID)

        pipeline = self.makim.global_data["pipelines"].get(pipeline_name)
        if not pipeline:
            MakimLogs.raise_error(f"Pipeline '{pipeline_name}' not found.", MakimError.MAKIM_TARGET_NOT_FOUND)

        return pipeline


    def execute_pipeline(self, pipeline_name: str, parallel=False, dry_run=False):
        """Executes a pipeline with optional debug logging."""
        pipeline = self.read_pipeline(pipeline_name)
        tasks = pipeline.get("tasks", [])
        continue_on_failure = pipeline.get("continue_on_failure", False)

        if not tasks:
            MakimLogs.raise_error(f"Pipeline '{pipeline_name}' has no tasks defined.")

        if self.debug:
            MakimLogs.print_info(f"[DEBUG] Pipeline '{pipeline_name}' has {len(tasks)} tasks.")

        sorted_tasks = self.topological_sort(tasks)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5) if parallel else None

        task_graph = {step["target"]: step for step in tasks}
        pending_tasks = set(sorted_tasks)

        while pending_tasks:
            executable_tasks = [
                task_name
                for task_name in pending_tasks
                if all(self.task_state.get(dep) == "SUCCESS" for dep in task_graph[task_name]["depends_on"])
            ]

            if not executable_tasks:
                MakimLogs.raise_error(f"Pipeline '{pipeline_name}' has unresolved dependencies.")
                return

            futures = []
            for task_name in executable_tasks:
                step = task_graph[task_name]
                retries = step.get("retries", 0)

                if self.debug:
                    MakimLogs.print_info(f"[DEBUG] Executing task '{task_name}', retries allowed: {retries}")

                if dry_run:
                    MakimLogs.print_info(f"[DRY-RUN] Task '{task_name}' would be executed.")
                else:
                    if parallel:
                        futures.append(executor.submit(self.execute_task, task_name, retries))
                    else:
                        self.execute_task(task_name, retries)

                pending_tasks.remove(task_name)

            if parallel and not dry_run:
                concurrent.futures.wait(futures)

        if parallel and not dry_run:
            executor.shutdown()

        if self.failed_tasks:
            MakimLogs.generate_error_report(self.failed_tasks)

        if continue_on_failure:
            MakimLogs.print_info(f"Pipeline '{pipeline_name}' completed with errors, but continued execution.")
        else:
            MakimLogs.print_info(f"Pipeline '{pipeline_name}' completed successfully.")

    def execute_task(self, task_name, retries):
        """Executes a task and logs debug information."""
        attempt = 0
        while attempt <= retries:
            try:
                if self.debug:
                    MakimLogs.print_info(f"[DEBUG] Running task '{task_name}', attempt {attempt + 1}/{retries + 1}")

                self.makim.run({"task": task_name})
                self.task_state[task_name] = "SUCCESS"

                if self.debug:
                    MakimLogs.print_info(f"[DEBUG] Task '{task_name}' completed successfully.")
                return True

            except Exception as e:
                attempt += 1
                error_message = f"Attempt {attempt}/{retries} failed. Error: {e}"
                MakimLogs.log_failure(task_name, error_message)

        self.task_state[task_name] = "FAILED"
        self.failed_tasks[task_name] = error_message
        return False

    def get_makim_instance():
        """Lazy import to prevent circular import issue."""
        from src.makim.core import Makim
        return Makim()


