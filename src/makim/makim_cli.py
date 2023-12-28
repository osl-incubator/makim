"""
Makim CLI module.

This module defines the command-line interface for the Makim tool.
"""
import os

from pathlib import Path

from typer import Argument, Option, Typer, echo
from typing_extensions import Annotated

from makim import Makim, __version__

makim = Makim()
app = Typer(
    name='Makim',
    epilog=(
        'If you have any problem, open an issue at: '
        'https://github.com/osl-incubator/makim'
    ),
)
makim_file_default = str(Path(os.getcwd()) / '.makim.yaml')


@app.callback(invoke_without_command=True)
def main(
    # Common Options
    help: bool = Option(
        None,
        '--help',
        '-h',
        is_flag=True,
        help='Show the version and exit',
    ),
    version: bool = Option(
        None,
        '--version',
        '-v',
        is_flag=True,
        help='Show the version and exit',
    ),
    verbose: bool = Option(
        None,
        '--verbose',
        is_flag=True,
        help='Show the commands to be executed.',
    ),
    dry_run: bool = Option(
        None,
        '--dry-run',
        is_flag=True,
        help="Show the commands but don't execute them.",
    ),
    # Makim-specific Options
    makim_file: Annotated[
        str,
        Option(
            '--makim-file',
            help='Specify a custom location for the makim file.',
            is_flag=True,
        ),
    ] = makim_file_default,
    target: Annotated[
        str,
        Argument(
            ...,
            help='Specify the target command to be performed.',
        ),
    ] = '',
):
    """
    Makim is a tool.

    that helps you to organize and simplify your helper commands.
    """
    if version:
        return show_version()

    if help or not target:
        return create_help_text(makim_file)

    args = {
        'dry_run': dry_run,
        'help': help,
        'makim_file': makim_file,
        'target': target,
        'verbose': verbose,
        'version': version,
    }

    makim.load(makim_file)
    return makim.run(args)


def create_help_text(makim_file):
    """Display help text with details about Makim commands and options."""
    usage = """makim [--help] [--version] [--verbose] [--dry-run] [--makim-file
    MAKIM_FILE] [target]"""

    description = """Makim is a tool that helps you to organize and simplify
    your helper commands."""

    epilog = """If you have any problem, open an issue at:
    https://github.com/osl-incubator/makim"""

    makim.load(makim_file)
    target_help = []

    # Iterate through groups and targets to generate help text
    groups = makim.global_data.get('groups', [])
    for group in groups:
        target_help.append('\n' + group + ':' + '\n')
        target_help.append('-' * (len(group) + 1) + '\n')
        for target_name, target_data in groups[group]['targets'].items():
            target_name_qualified = f'{group}.{target_name}'
            help_text = target_data['help'] if 'help' in target_data else ''
            target_help.append(f'  {target_name_qualified} => {help_text}\n')

            if 'args' in target_data:
                target_help.append('    ARGS:\n')

                for arg_name, arg_data in target_data['args'].items():
                    target_help.append(
                        f'      --{arg_name}: ({arg_data["type"]}) '
                        f'{arg_data["help"]}\n'
                    )

    help_text = format_help_text(description, usage, epilog, target_help)
    echo(help_text)


def format_help_text(description, usage, epilog, target_help):
    """Format help text with usage, description, and target details."""
    return f"""{usage}

{description}

Positonal Arguments:
{"".join(target_help)}
{epilog}"""


def show_version():
    """Show version."""
    echo(__version__)


if __name__ == '__main__':
    app()
