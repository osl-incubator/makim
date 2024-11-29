"""Cli functions to define the arguments and to call Makim."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Type, Union, cast

import click
import typer  # noqa

from fuzzywuzzy import process
from typer import Typer

from makim.core import Makim


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


def create_dynamic_command(
    makim: Makim, app: Typer, name: str, args: dict[str, str]
) -> None:
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
    global_vars: dict[str, Any] = globals()
    global_vars['makim'] = makim

    exec(function_code, global_vars, local_vars)
    dynamic_command = decorator(local_vars['dynamic_command'])

    # Apply Click options to the Typer command
    if 'args' in args:
        options_data = cast(Dict[str, Dict[str, Any]], args.get('args', {}))
        dynamic_command = apply_click_options(dynamic_command, options_data)


def create_dynamic_command_cron(
    makim: Makim, app: Typer, name: str, args: dict[str, str]
) -> None:
    """
    Dynamically create a Typer command with the specified options.

    Parameters
    ----------
    name : str
        The command name.
    args : dict
        The command arguments and options.
    """
    args_param_list = [f'"task": "{name}"']
    args_param_str = '{' + ','.join(args_param_list) + '}'
    group_name = 'cron'

    decorator = app.command(
        name,
        help=args.get('help', ''),
        rich_help_panel=group_name,
    )

    function_code = 'def dynamic_command():\n'
    function_code += f'    makim.run({args_param_str})\n'

    local_vars: dict[str, Any] = {}
    global_vars: dict[str, Any] = globals()
    global_vars['makim'] = makim

    exec(function_code, global_vars, local_vars)
    decorator(local_vars['dynamic_command'])
