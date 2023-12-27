"""
Makim CLI module.

This module defines the command-line interface for the Makim tool.
"""
import os
import sys

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
):# noqa: PLR0913
    """
    Makim is a tool.

    that helps you to organize and simplify your helper commands.
    """
    makim_args = extract_makim_args()
    print('Makim-Args: ', makim_args)

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
    makim_args.update(args)

    print('After update, Makim_Args: ', makim_args)

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


def extract_makim_args():
    """Extract makim arguments from the CLI call."""
    makim_args = {}
    index_to_remove = []
    for ind, arg in enumerate(list(sys.argv)):
        if arg in [
            '--help',
            '--version',
            '--verbose',
            '--makim-file',
            '--dry-run',
        ]:
            continue

        if not arg.startswith('--'):
            continue

        index_to_remove.append(ind)

        arg_name = None
        arg_value = None

        next_ind = ind + 1

        arg_name = sys.argv[ind]

        if (
            len(sys.argv) == next_ind
            or len(sys.argv) > next_ind
            and sys.argv[next_ind].startswith('--')
        ):
            arg_value = True
        else:
            arg_value = sys.argv[next_ind]
            index_to_remove.append(next_ind)

        makim_args[arg_name] = arg_value

    # remove exclusive makim flags from original sys.argv
    for ind in sorted(index_to_remove, reverse=True):
        sys.argv.pop(ind)

    return makim_args


if __name__ == '__main__':
    app()
