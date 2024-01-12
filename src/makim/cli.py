"""Cli functions to define the arguments and to call Makim."""
from __future__ import annotations

from typing import Any, Callable

import click
import typer

from makim import Makim, __version__

app = typer.Typer(
    help=(
        'Makim is a tool that helps you to organize '
        'and simplify your helper commands.'
    ),
    epilog=(
        'If you have any problem, open an issue at: '
        'https://github.com/osl-incubator/makim'
    ),
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        '--version',
        '-v',
        is_flag=True,
        help='Show the version and exit.',
    ),
) -> None:
    """Process envers for specific flags, otherwise show the help menu."""
    if version:
        typer.echo(f'Version: {__version__}')
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


def type_mapper(type_name):
    """
    Return a mapped string representation of a type to the actual Python type.

    Parameters
    ----------
    type_name : str
        The string representation of the type.

    Returns
    -------
    type
        The corresponding Python type.
    """
    type_mapping = {
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        # Add more mappings as needed
    }
    return type_mapping.get(type_name, str)


def create_args_string(args: dict[str, str]) -> str:
    """Return a string for arguments for a function for typer."""
    args_rendered = []

    arg_template = (
        '{arg_name}: {arg_type} = typer.Option('
        '{default_value}, '
        '"--{name_flag}", '
        'help="{help_text}"'
        ')'
    )

    for name, spec in args.get('args', {}).items():
        name_clean = name.replace('-', '_')
        arg_type = spec.get('type', 'str')
        help_text = spec.get('help', '')
        default_value = spec.get('default')

        if default_value and spec['type'] == 'str':
            default_value = f'"{default_value}"'
        else:
            default_value = f'{default_value}'

        arg_str = arg_template.format(
            **{
                'arg_name': name_clean,
                'arg_type': arg_type,
                'default_value': default_value,
                'name_flag': name,
                'help_text': help_text,
            }
        )
        args_rendered.append(arg_str)

    return ''.join(args_rendered)


def apply_click_options(
    command_function: Callable, options: dict[str, str]
) -> Callable:
    """
    Apply Click options to a Typer command function.

    Parameters
    ----------
    command_function : callable
        The Typer command function to which options will be applied.
    options : dict
        A dictionary of options to apply.

    Returns
    -------
    callable
        The command function with options applied.
    """
    for opt_name, opt_details in options.items():
        click_option = click.option(
            f'--{opt_name}',
            default=opt_details.get('default'),
            type=type_mapper(opt_details.get('type', 'str')),
            help=opt_details.get('help', ''),
        )
        command_function = click_option(command_function)

    return command_function


def create_dynamic_command(name: str, args: dict[str, str]) -> None:
    """
    Dynamically create a Typer command with the specified options.

    Parameters
    ----------
    name : str
        The command name.
    args : dict
        The command arguments and options.
    """
    args_str = create_args_string(args)

    decorator = app.command(name=name, help=args['help'])

    function_code = (
        f'def dynamic_command({args_str}):\n'
        "    typer.echo(f'Executing ' + name)\n"
        '\n'
    )

    local_vars = {}
    exec(function_code, globals(), local_vars)
    dynamic_command = decorator(local_vars['dynamic_command'])

    # Apply Click options to the Typer command
    if 'args' in args:
        dynamic_command = apply_click_options(dynamic_command, args['args'])


def run_app() -> None:
    makim = Makim()
    makim.load('.makim.yaml')

    # create targets data
    group_names = list(makim.global_data.get('groups', {}).keys())
    targets: dict[str, Any] = {}
    for group_name, group_data in makim.global_data.get('groups', {}).items():
        for target_name, target_data in group_data.get('targets', {}).items():
            targets[f'{group_name}.{target_name}'] = target_data

    # Add dynamically created commands to Typer app
    for name, args in targets.items():
        create_dynamic_command(name, args)
    app()


if __name__ == '__main__':
    run_app()
