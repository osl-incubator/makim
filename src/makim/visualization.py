from rich.console import Console
from rich.tree import Tree

try:
    from asciinet import Graph  # Ensure asciinet is installed
    ASCIINET_AVAILABLE = True
except ImportError:
    ASCIINET_AVAILABLE = False

console = Console()


class PipelineVisualizer:
    """Handles the conversion of pipelines into an ASCII graph or tree structure."""

    @staticmethod
    def render_tree(pipeline_name, pipeline_data):
        """Displays the pipeline as a hierarchical tree structure."""
        tree = Tree(f"[bold cyan]Pipeline: {pipeline_name}[/bold cyan]")

        task_nodes = {}

        for task in pipeline_data:
            task_name = task["target"]
            dependencies = task.get("depends_on", [])

            if task_name not in task_nodes:
                task_nodes[task_name] = tree.add(f"🟢 {task_name}")

            for dep in dependencies:
                if dep not in task_nodes:
                    task_nodes[dep] = tree.add(f"🔵 {dep}")

                task_nodes[dep].add(task_nodes[task_name])

        console.print(tree)

    @staticmethod
    def render_graph(pipeline_name, pipeline_data):
        """Displays the pipeline as an ASCII graph using asciinet."""
        if not ASCIINET_AVAILABLE:
            console.print("[red]Error: 'asciinet' package is not installed. Install it with 'pip install asciinet'.[/red]")
            return

        dag = Graph()

        for task in pipeline_data:
            task_name = task["target"]
            depends_on = task.get("depends_on", [])

            for dep in depends_on:
                dag.add_edge(dep, task_name)

        console.print(dag.render())
