import typer
from makim.core import Makim

def run_pipeline(pipeline_name: str, parallel: bool = False, debug: bool = False, dry_run: bool = False):
    """Execute a pipeline with optional parallel, debug, and dry-run modes."""
    makim = Makim(debug=debug)
    makim.start_pipeline(pipeline_name, parallel=parallel, dry_run=dry_run)


def show_pipeline(pipeline_name: str, graph: bool = False):
    """Display the structure of a defined pipeline."""
    makim = Makim()
    pipeline_data = makim.get_pipeline_structure(pipeline_name)

    if not pipeline_data:
        typer.echo(f"Pipeline '{pipeline_name}' not found.")
        return

    typer.echo(f"Pipeline '{pipeline_name}':")
    for task in pipeline_data:
        typer.echo(f" - {task['target']} (Depends on: {', '.join(task.get('depends_on', []))})")

