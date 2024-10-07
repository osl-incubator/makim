"""Cli functions to define the arguments and to call Makim."""

from __future__ import annotations

import os
import sys

from typing import Any, Callable, Dict, Optional, Type, Union, cast

import click
import typer

from fuzzywuzzy import process

from makim import __version__
from makim.core import Makim

CLI_ROOT_FLAGS_VALUES_COUNT = {
    '--dry-run': 0,
    '--file': 1,
    '--help': 0,  # not necessary to store this value
    '--verbose': 0,
    '--version': 0,  # not necessary to store this value
}

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

makim: Makim = Makim()


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
    verbose: bool = typer.Option(
        None,
        '--verbose',
        is_flag=True,
        help='Execute the command in verbose mode',
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


def suggest_command(user_input: str, available_commands: list[str]) -> str:
    """
    Suggest the closest command to the user input using fuzzy search.

    Parameters
    ----------
    user_input (str): The command input by the user.
    available_commands (list): A list of available commands.

    Returns
    -------
    str: The suggested command.
    """
    suggestion, _ = process.extractOne(user_input, available_commands)
    return str(suggestion)


def map_type_from_string(type_name: str) -> Type[Union[str, int, float, bool]]:
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


def normalize_string_type(type_name: str) -> str:
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


def get_default_value(
    arg_type: str, value: Any
) -> Optional[Union[str, int, float, bool]]:
    """Return the default value regarding its type in a string format."""
    if arg_type == 'bool':
        return False if value is None else bool(value)
    elif arg_type == 'int':
        return int(value) if value is not None else None
    elif arg_type == 'float':
        return float(value) if value is not None else None
    elif arg_type == 'str':
        return str(value) if value is not None else None
    return None


def get_default_value_str(arg_type: str, value: Any) -> str:
    """Return the default value regarding its type in a string format."""
    if arg_type == 'str':
        return f'"{value}"'

    if arg_type == 'bool':
        return 'False'

    return f'{value or 0}'


def create_args_string(args: dict[str, str]) -> str:
    """Return a string for arguments for a function for typer."""
    args_rendered = []

    arg_template = (
        '{arg_name}: Optional[{arg_type}] = typer.Option('
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
        default_value = 'None'

        if not spec.get('required', False) and not spec.get(
            'interactive', False
        ):
            default_value = spec.get('default', '')
            default_value = get_default_value_str(arg_type, default_value)

        arg_str = arg_template.format(
            **{
                'arg_name': name_clean,
                'arg_type': arg_type,
                'default_value': default_value,
                'name_flag': name,
                'help_text': help_text.replace('\n', '\\n'),
            }
        )

        args_rendered.append(arg_str)

    return ', '.join(args_rendered)


def apply_click_options(
    command_function: Callable[..., Any], options: dict[str, Any]
) -> Callable[..., Any]:
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
        opt_args: dict[
            str, Optional[Union[str, int, float, bool, Type[Any]]]
        ] = {}

        opt_data = cast(Dict[str, str], opt_details)
        opt_type_str = normalize_string_type(opt_data.get('type', 'str'))
        opt_default = get_default_value(opt_type_str, opt_data.get('default'))

        if opt_type_str == 'bool':
            opt_args.update({'is_flag': True})

        opt_args.update(
            {
                'default': None
                if opt_data.get('interactive', False)
                else opt_default,
                'type': map_type_from_string(opt_type_str),
                'help': opt_data.get('help', ''),
                'show_default': True,
            }
        )

        click_option = click.option(
            f'--{opt_name}',
            **opt_args,  # type: ignore[arg-type]
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
    args_param_list = [f'"task": "{name}"']

    args_data = cast(Dict[str, Dict[str, str]], args.get('args', {}))

    for arg, arg_details in args_data.items():
        arg_clean = arg.replace('-', '_')
        args_param_list.append(f'"--{arg}": {arg_clean}')

    args_param_str = '{' + ','.join(args_param_list) + '}'
    group_name = name.split('.')[0]

    decorator = app.command(
        name,
        help=args.get('help', ''),
        rich_help_panel=group_name,
    )

    function_code = f'def dynamic_command({args_str}):\n'

    # handle interactive prompts
    for arg, arg_details in args_data.items():
        arg_clean = arg.replace('-', '_')
        if arg_details.get('interactive', False):
            function_code += f'    if {arg_clean} is None:\n'
            function_code += f"        {arg_clean} = click.prompt('{arg}')\n"

    function_code += f'    makim.run({args_param_str})\n'

    local_vars: dict[str, Any] = {}
    exec(function_code, globals(), local_vars)
    dynamic_command = decorator(local_vars['dynamic_command'])

    # Apply Click options to the Typer command
    if 'args' in args:
        options_data = cast(Dict[str, Dict[str, Any]], args.get('args', {}))
        dynamic_command = apply_click_options(dynamic_command, options_data)


def extract_root_config(
    cli_list: list[str] = sys.argv,
) -> dict[str, str | bool]:
    """Extract the root configuration from the CLI."""
    params = cli_list[1:]

    # default values
    makim_file = '.makim.yaml'
    dry_run = False
    verbose = False

    try:
        idx = 0
        while idx < len(params):
            arg = params[idx]
            if arg not in CLI_ROOT_FLAGS_VALUES_COUNT:
                break

            if arg == '--file':
                try:
                    makim_file = params[idx + 1]
                except IndexError:
                    pass
            elif arg == '--dry-run':
                dry_run = True
            elif arg == '--verbose':
                verbose = True

            idx += 1 + CLI_ROOT_FLAGS_VALUES_COUNT[arg]
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
        'verbose': verbose,
    }


def _get_command_from_cli() -> str:
    """
    Get the group and task from CLI.

    This function is based on `CLI_ROOT_FLAGS_VALUES_COUNT`.
    """
    params = sys.argv[1:]
    command = ''

    try:
        idx = 0
        while idx < len(params):
            arg = params[idx]
            if arg not in CLI_ROOT_FLAGS_VALUES_COUNT:
                command = f'flag `{arg}`' if arg.startswith('--') else arg
                break

            idx += 1 + CLI_ROOT_FLAGS_VALUES_COUNT[arg]
    except Exception as e:
        print(e)

    return command


def run_app() -> None:
    """Run the typer app."""
    root_config = extract_root_config()

    config_file_path = cast(str, root_config.get('file', '.makim.yaml'))

    cli_completion_words = [
        w for w in os.getenv('COMP_WORDS', '').split('\n') if w
    ]

    if not makim._check_makim_file(config_file_path) and cli_completion_words:
        # autocomplete call
        root_config = extract_root_config(cli_completion_words)
        config_file_path = cast(str, root_config.get('file', '.makim.yaml'))
        if not makim._check_makim_file(config_file_path):
            return

    makim.load(
        file=config_file_path,
        dry_run=cast(bool, root_config.get('dry_run', False)),
        verbose=cast(bool, root_config.get('verbose', False)),
    )

    # create tasks data
    # group_names = list(makim.global_data.get('groups', {}).keys())
    tasks: dict[str, Any] = {}
    for group_name, group_data in makim.global_data.get('groups', {}).items():
        for task_name, task_data in group_data.get('tasks', {}).items():
            tasks[f'{group_name}.{task_name}'] = task_data

    # Add dynamically created commands to Typer app
    for name, args in tasks.items():
        create_dynamic_command(name, args)
    try:
        app()
    except SystemExit as e:
        # code 2 means code not found
        error_code = 2
        if e.code != error_code:
            raise e

        command_used = _get_command_from_cli()

        available_cmds = [
            cmd.name for cmd in app.registered_commands if cmd.name is not None
        ]
        suggestion = suggest_command(command_used, available_cmds)

        typer.secho(
            f"Command {command_used} not found. Did you mean '{suggestion}'?",
            fg='red',
        )

        raise e


if __name__ == '__main__':
    run_app()
