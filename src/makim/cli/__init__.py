"""Minimal custom parser for Makim without external dependencies."""

import sys  # Keep this import

from typing import Any, Dict, List, Optional

# We need to be careful with imports to avoid circular imports
from .. import __version__
from ..core import Makim


def parse_args(args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Parse command-line arguments using a simple approach.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns
    -------
        Dictionary of parsed arguments
    """
    if args is None:
        args = sys.argv[1:]

    result = {
        'file': '.makim.yaml',
        'dry_run': False,
        'verbose': False,
        'skip_hooks': False,
    }

    # Process all arguments
    i = 0
    cmd_found = False
    task_found = False

    while i < len(args):
        arg = args[i]

        # Handle options
        if arg in ('--version', '-v'):
            result['version'] = True
            i += 1
        elif arg in ('--file', '-f'):
            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                result['file'] = args[i + 1]
                i += 2
            else:
                print('Error: --file requires a value', file=sys.stderr)
                i += 1
        elif arg == '--dry-run':
            result['dry_run'] = True
            i += 1
        elif arg == '--verbose':
            result['verbose'] = True
            i += 1
        elif arg == '--skip-hooks':
            result['skip_hooks'] = True
            i += 1
        # Handle commands
        elif not arg.startswith('-') and not cmd_found:
            result['command'] = arg
            cmd_found = True
            i += 1

            # If command is 'run', next argument is the task
            if (
                arg == 'run'
                and i < len(args)
                and not args[i].startswith('-')
                and not task_found
            ):
                result['task'] = args[i]
                task_found = True
                i += 1
        else:
            # Skip unknown argument
            i += 1

    return result


def show_help() -> int:
    """Display help information."""
    print('Makim: Task execution system')
    print('\nUsage:')
    print('  makim [options] <command> [args]')
    print('\nCommands:')
    print('  list              List available tasks')
    print('  run <task>        Run a specific task')
    print('\nOptions:')
    print('  --version, -v     Show version and exit')
    print('  --file, -f FILE   Config file (default: .makim.yaml)')
    print('  --dry-run         Execute in dry-run mode')
    print('  --verbose         Show verbose output')
    print('  --skip-hooks      Skip hooks while executing')
    return 0


def list_tasks(makim: Makim) -> int:
    """List all available tasks."""
    if not hasattr(makim, 'global_data') or not makim.global_data:
        print('No tasks found.')
        return 0

    print('Available tasks:')
    for group_name, group_data in makim.global_data.get('groups', {}).items():
        if not group_data.get('tasks'):
            continue

        for task_name in group_data['tasks']:
            task_path = f'{group_name}.{task_name}'
            task_desc = group_data['tasks'][task_name].get('description', '')
            print(f'  {task_path:<30} {task_desc}')

    return 0


def run_task(makim: Makim, task: str, options: Dict[str, Any]) -> int:
    """Run a specific task with options."""
    if not task:
        print('Error: No task specified', file=sys.stderr)
        return 1

    # Execute task
    try:
        task_options = {
            'task': task,
            'dry_run': options.get('dry_run', False),
            'verbose': options.get('verbose', False),
            'skip_hooks': options.get('skip_hooks', False),
        }
        makim.run(task_options)
        return 0
    except Exception as e:
        print(f'Error running task: {e}', file=sys.stderr)
        return 1


def run_app() -> int:
    """Run Makim with custom parser."""
    try:
        # Parse arguments
        args = parse_args()

        # Create Makim instance
        makim = Makim()

        # Handle --version
        if args.get('version'):
            print(f'Version: {__version__}')
            return 0

        # Get file path
        file_path = args.get('file', '.makim.yaml')
        print(f'Makim file: {file_path}')

        # Handle commands
        cmd = args.get('command')

        # No command or unknown command - show help
        if not cmd or cmd not in ('list', 'run'):
            return show_help()

        # Load makim configuration
        makim.load(file=file_path)

        # Execute the appropriate command
        if cmd == 'list':
            return list_tasks(makim)
        else:  # cmd == 'run'
            return run_task(makim, args.get('task', ''), args)

    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(run_app())
