"""Cli functions to define the arguments and to call Makim."""
from __future__ import annotations

import sys

from typing import Any, Callable, Dict, Type, cast

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

makim = Makim()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        '--version',
        '-v',
        is_flag=True,
        help='Show the version and exit',
    ),
    file: str = typer.Option(
        '.makim.yaml',
        '--file',
        help='Makim config file',
    ),
    dry_run: bool = typer.Option(
        None,
        '--dry-run',
        is_flag=True,
        help='Execute the command in dry mode',
    ),
) -> None:
    """Process envers for specific flags, otherwise show the help menu."""
    typer.echo(f'Makim file: {file}')

    if version:
        typer.echo(f'Version: {__version__}')
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


def map_type_from_string(type_name) -> Type:
    """
    Return a type object mapped from the type name.

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
        'string': str,
        'int': int,
        'integer': int,
        'float': float,
        'bool': bool,
        'boolean': bool,
    }
    return type_mapping.get(type_name, str)


def normalize_string_type(type_name) -> str:
    """
    Normalize the user type definition to the correct name.

    Parameters
    ----------
    type_name : str
        The string representation of the type.

    Returns
    -------
    str
        The corresponding makim type name.
    """
    type_mapping = {
        'str': 'str',
        'string': 'str',
        'int': 'int',
        'integer': 'int',
        'float': 'float',
        'bool': 'bool',
        'boolean': 'bool',
        # Add more mappings as needed
    }
    return type_mapping.get(type_name, 'str')


def create_args_string(args: Dict[str, str]) -> str:
    """Return a string for arguments for a function for typer."""
    args_rendered = []

    arg_template = (
        '{arg_name}: {arg_type} = typer.Option('
        '{default_value}, '
        '"--{name_flag}", '
        'help="{help_text}"'
        ')'
    )

    args_data = cast(Dict[str, Dict[str, str]], args.get('args', {}))
    for name, spec in args_data.items():
        name_clean = name.replace('-', '_')
        arg_type = normalize_string_type(spec.get('type', 'str'))
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
    command_function: Callable, options: Dict[str, str]
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
        opt_data = cast(Dict[str, str], opt_details)
        click_option = click.option(
            f'--{opt_name}',
            default=opt_data.get('default'),
            type=map_type_from_string(opt_data.get('type', 'str')),
            help=opt_data.get('help', ''),
        )
        command_function = click_option(command_function)

    return command_function


def create_dynamic_command(name: str, args: Dict[str, str]) -> None:
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
    args_param_list = [f'"target": "{name}"']

    args_data = cast(Dict[str, str], args.get('args', {}))

    for arg in list(args_data.keys()):
        args_param_list.append(f'"{arg}": {arg}')

    args_param_str = '{' + ','.join(args_param_list) + '}'
    decorator = app.command(name, help=args['help'])

    function_code = (
        f'def dynamic_command({args_str}):\n'
        f'    makim.run({args_param_str})\n'
        '\n'
    )

    local_vars: Dict[str, Any] = {}
    exec(function_code, globals(), local_vars)
    dynamic_command = decorator(local_vars['dynamic_command'])

    # Apply Click options to the Typer command
    if 'args' in args:
        options_data = cast(Dict[str, str], args.get('args', {}))
        dynamic_command = apply_click_options(dynamic_command, options_data)


def extract_root_config() -> Dict[str, str | bool]:
    """Extract the root configuration from the CLI."""
    params = sys.argv[1:]

    root_args_values_count = {
        '--dry-run': 0,
        '--file': 1,
        '--help': 0,  # not necessary to store this value
        '--version': 0,  # not necessary to store this value
    }

    # default values
    makim_file = '.makim.yaml'
    dry_run = False

    try:
        idx = 0
        while idx < len(params):
            arg = params[idx]
            if arg not in root_args_values_count:
                break

            if arg == '--file':
                makim_file = params[idx + 1]

            elif arg == '--dry-run':
                dry_run = True

            idx += 1 + root_args_values_count[arg]
    except Exception:
        red_text = typer.style(
            'The makim config file was not correctly detected. '
            'Using the default .makim.yaml.',
            fg=typer.colors.RED,
            bold=True,
        )
        typer.echo(red_text, err=True, color=True)

    return {
        'file': makim_file,
        'dry_run': dry_run,
    }


def run_app() -> None:
    """Run the typer app."""
    root_config = extract_root_config()

    makim.load(
        file=cast(str, root_config.get('file', '.makim.yaml')),
        dry_run=cast(bool, root_config.get('dry_run', False)),
    )

    # create targets data
    # group_names = list(makim.global_data.get('groups', {}).keys())
    targets: Dict[str, Any] = {}
    for group_name, group_data in makim.global_data.get('groups', {}).items():
        for target_name, target_data in group_data.get('targets', {}).items():
            targets[f'{group_name}.{target_name}'] = target_data

    # Add dynamically created commands to Typer app
    for name, args in targets.items():
        create_dynamic_command(name, args)

    app()


if __name__ == '__main__':
    run_app()
