"""Makim core module."""

from __future__ import annotations

import copy
import io
import json
import os
import pprint
import shutil
import sys
import tempfile
import warnings

from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Union, cast

import dotenv
import paramiko
import sh
import yaml

from jinja2 import Environment
from jsonschema import ValidationError, validate
from typing_extensions import TypeAlias

from makim.console import get_terminal_size
from makim.logs import MakimError, MakimLogs
from makim.scheduler import MakimScheduler


def command_exists(command: str) -> bool:
    """Check if a system command exists in PATH."""
    return shutil.which(command) is not None


if getattr(sys, 'frozen', False):
    MAKIM_CURRENT_PATH = Path(sys._MEIPASS)  # type: ignore
else:
    MAKIM_CURRENT_PATH = Path(__file__).parent

AppConfigType: TypeAlias = Dict[str, Union[str, List[str]]]

SCOPE_GLOBAL = 0
SCOPE_GROUP = 1
SCOPE_TARGET = 2

# note: this is necessary for the executable version (pyinstaller)
DEFAULT_SHELL_NAME = (
    'xonsh'
    if command_exists('xonsh')
    else 'bash'
    if command_exists('bash')
    else 'zsh'
    if command_exists('zsh')
    else 'sh'
    if command_exists('sh')
    else ''
)

if not DEFAULT_SHELL_NAME:
    MakimLogs.raise_error(
        'No backend found (xonsh, bash, zsh, sh).',
        MakimError.MAKIM_NO_BACKEND_FOUND,
    )

MakimLogs.print_info(f' DEFAULT SHELL: {DEFAULT_SHELL_NAME}')
DEFAULT_SHELL_APP = getattr(sh, DEFAULT_SHELL_NAME)

KNOWN_SHELL_APP_ARGS = {
    'bash': ['-e'],
    'php': ['-f'],
    'nox': ['-f'],
}

# useful when the program just read specific file extension
KNOWN_SHELL_APP_FILE_SUFFIX = {
    'nox': '.makim.py',
}

TEMPLATE = Environment(
    autoescape=False,
    variable_start_string='${{',
    variable_end_string='}}',
)


class HostConfig(TypedDict):
    """
    Type definition for SSH host configuration containing.

    Includes username, host, port, and optional password.
    """

    username: str
    host: str
    port: int
    password: Optional[str]


def strip_recursively(data: Any) -> Any:
    """Strip strings in list and dictionaries."""
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, list):
        return [strip_recursively(item) for item in data]
    if isinstance(data, dict):
        return {k: strip_recursively(v) for k, v in data.items()}
    return data


def fix_dict_keys_recursively(data: Any) -> Any:
    """Replicate dictionary key with `-` to `_` recursively."""
    if not isinstance(data, (list, dict)):
        return data

    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (list, dict)):
                data[i] = fix_dict_keys_recursively(item)
        return data

    # data is a dictionary
    for k, v in copy.deepcopy(data).items():
        if not isinstance(v, (list, dict)):
            if '-' in k:
                data[k.replace('-', '_')] = copy.deepcopy(v)
            continue
        data[k] = fix_dict_keys_recursively(v)
        if '-' in k:
            data[k.replace('-', '_')] = copy.deepcopy(v)
    return data


class Makim:
    """Makim main class."""

    file: str = '.makim.yaml'
    dry_run: bool = False
    verbose: bool = False
    global_data: dict[str, Any] = {}
    shell_app: sh.Command = DEFAULT_SHELL_APP
    shell_args: list[str] = []
    tmp_suffix: str = '.makim'

    # temporary variables
    env: dict[str, Any] = {}  # initial env
    env_scoped: dict[str, Any] = {}  # current env
    # initial working directory
    working_directory: Optional[Path] = None
    # current working directory
    working_directory_scoped: Optional[Path] = None
    args: Optional[dict[str, Any]] = None
    group_name: str = 'default'
    group_data: dict[str, Any] = {}
    task_name: str = ''
    task_data: dict[str, Any] = {}
    ssh_config: dict[str, Any] = {}
    scheduler: Optional[MakimScheduler] = None

    def __init__(self) -> None:
        """Prepare the Makim class with the default configuration."""
        os.environ['RAISE_SUBPROC_ERROR'] = '1'
        os.environ['XONSH_SHOW_TRACEBACK'] = '0'

        # default
        self.file = '.makim.yaml'
        self.dry_run = False
        self.verbose = False
        self.shell_app = DEFAULT_SHELL_APP
        self.shell_args: list[str] = []
        self.tmp_suffix: str = '.makim'
        self.scheduler = None
        # os.chdir(os.getcwd())

    def __getstate__(self) -> Dict[str, Any]:
        """Return a serializable state of the Makim instance."""
        state: Dict[str, Any] = self.__dict__.copy()
        if 'scheduler' in state:
            state['scheduler'] = None
        return state

    def _call_shell_app(self, cmd: str) -> None:
        self._load_shell_app()

        fd, filepath = tempfile.mkstemp(suffix=self.tmp_suffix, text=True)

        with open(filepath, 'w') as f:
            f.write(cmd)

        p = self.shell_app(
            *self.shell_args,
            filepath,
            _in=sys.stdin,
            _out=sys.stdout,
            _err=sys.stderr,
            _bg=True,
            _bg_exc=False,
            _no_err=True,
            _env=os.environ,
            _new_session=True,
            _cwd=str(self._resolve_working_directory('task')),
        )

        try:
            p.wait()
        except sh.ErrorReturnCode as e:
            os.close(fd)
            MakimLogs.raise_error(
                str(e.full_cmd),
                MakimError.SH_ERROR_RETURN_CODE,
                e.exit_code or 1,
            )
        except KeyboardInterrupt:
            os.close(fd)
            pid = p.pid
            p.kill_group()
            MakimLogs.raise_error(
                f'Process {pid} killed.',
                MakimError.SH_KEYBOARD_INTERRUPT,
            )
        os.close(fd)

    def _call_shell_remote(
        self, cmd: str, host_config: dict[str, Any]
    ) -> None:
        try:
            # Render the host configuration values
            env, variables = self._load_scoped_data('task')
            rendered_config = self._render_host_config(host_config, env)

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                username=rendered_config['username'],
                password=rendered_config.get('password'),
                hostname=rendered_config['host'],
                port=rendered_config['port'],
            )

            stdin, stdout, stderr = ssh.exec_command(
                cmd, environment=os.environ
            )

            if self.verbose:
                MakimLogs.print_info(cmd)

            MakimLogs.print_info(stdout.read().decode('utf-8'))

            error = stderr.read().decode('utf-8')
            if error:
                MakimLogs.raise_error(error, MakimError.SSH_EXECUTION_ERROR)

            ssh.close()
        except paramiko.AuthenticationException:
            MakimLogs.raise_error(
                f'Authentication failed for host {host_config["host"]}',
                MakimError.SSH_AUTHENTICATION_FAILED,
            )
        except paramiko.SSHException as ssh_exception:
            MakimLogs.raise_error(
                f'SSH error: {ssh_exception!s}',
                MakimError.SSH_CONNECTION_ERROR,
            )
        except Exception as e:
            MakimLogs.raise_error(
                f'Unexpected error during remote execution: {e!s}',
                MakimError.SSH_EXECUTION_ERROR,
            )

    def _render_host_config(
        self, host_config: dict[str, Any], env: dict[str, str]
    ) -> HostConfig:
        """Render the host configuration values using Jinja2 templates."""
        rendered: dict[str, Optional[str]] = {}

        for key in ('user', 'host', 'password', 'port'):
            value = host_config.get(key, '')
            str_value = str(value) if value is not None else ''

            if isinstance(value, str):
                str_value = TEMPLATE.from_string(str_value).render(env=env)

            if key == 'port':
                rendered[key] = str_value if str_value.isdigit() else '22'
            elif key == 'password':
                rendered[key] = str_value if str_value else None
            else:
                rendered[key] = str_value

        return cast(
            HostConfig,
            {
                'username': rendered['user'],
                'host': rendered['host'],
                'port': int(rendered['port']) if rendered['port'] else 22,
                'password': rendered['password'],
            },
        )

    def _check_makim_file(self, file_path: str = '') -> bool:
        return Path(file_path or self.file).absolute().exists()

    def _validate_config(self) -> None:
        """
        Validate the .makim.yaml against the predefined JSON Schema.

        Raises
        ------
            MakimError: If the configuration does not conform to the schema.
        """
        try:
            with open(MAKIM_CURRENT_PATH / 'schema.json', 'r') as schema_file:
                schema = json.load(schema_file)

            config_data = self.global_data

            # Validate the configuration against the schema
            validate(instance=config_data, schema=schema)

            if self.verbose:
                MakimLogs.print_info('Configuration validation successful.')

        except ValidationError as ve:
            error_message = f'Configuration validation error: {ve.message}'
            MakimLogs.raise_error(
                error_message, MakimError.CONFIG_VALIDATION_ERROR
            )
        except yaml.YAMLError as ye:
            error_message = f'YAML parsing error: {ye}'
            MakimLogs.raise_error(error_message, MakimError.YAML_PARSING_ERROR)
        except json.JSONDecodeError as je:
            error_message = f'JSON schema decoding error: {je}'
            MakimLogs.raise_error(
                error_message, MakimError.JSON_SCHEMA_DECODING_ERROR
            )
        except FileNotFoundError:
            error_message = 'Vaidation schema file not found.'
            MakimLogs.raise_error(
                error_message, MakimError.MAKIM_SCHEMA_FILE_NOT_FOUND
            )
        except Exception as e:
            error_message = (
                f'Unexpected error during configuration validation: {e}'
            )
            MakimLogs.raise_error(
                error_message, MakimError.CONFIG_VALIDATION_UNEXPECTED_ERROR
            )

    def _verify_task_conditional(self, conditional: Any) -> bool:
        # todo: implement verification
        print(f'condition {conditional} not verified')
        return False

    def _verify_args(self) -> None:
        if not self._check_makim_file():
            MakimLogs.raise_error(
                f'Makim file {self.file} not found.',
                MakimError.MAKIM_CONFIG_FILE_NOT_FOUND,
            )

    def _verify_config(self) -> None:
        if not len(self.global_data['groups']):
            MakimLogs.raise_error(
                'No task groups found.',
                MakimError.MAKIM_NO_TARGET_GROUPS_FOUND,
            )

    def _change_task(self, task_name: str) -> None:
        group_name = 'default'
        if '.' in task_name:
            group_name, task_name = task_name.split('.')

        self.task_name = task_name
        self._change_group_data(group_name)

        for task_name, task_data in self.group_data['tasks'].items():
            if task_name == self.task_name:
                self.task_data = task_data
                return

        MakimLogs.raise_error(
            f'The given task "{self.task_name}" was not found in the '
            f'configuration file for the group {self.group_name}.',
            MakimError.MAKIM_TARGET_NOT_FOUND,
        )

    def _change_group_data(self, group_name: Optional[str] = None) -> None:
        groups = self.global_data['groups']

        if group_name is not None:
            self.group_name = group_name

        if self.group_name not in groups and len(groups) == 1:
            self.group_name = next(iter(groups))

        for group in groups:
            if group == self.group_name:
                self.group_data = groups[group]
                return

        MakimLogs.raise_error(
            f'The given group task "{self.group_name}" '
            'was not found in the configuration file.',
            MakimError.MAKIM_GROUP_NOT_FOUND,
        )

    def _load_config_data(self) -> None:
        if not self._check_makim_file():
            MakimLogs.raise_error(
                f'Makim file {self.file} not found',
                MakimError.MAKIM_CONFIG_FILE_NOT_FOUND,
            )

        with open(Path(self.file).absolute(), 'r') as f:
            # escape template tags
            content = f.read()
            content_io = io.StringIO(content)
            self.global_data = yaml.safe_load(content_io)

        self.ssh_config = self.global_data.get('hosts', {})

        self._validate_config()

        if 'scheduler' in self.global_data:
            if self.scheduler is None:
                self.scheduler = MakimScheduler(self)

    def _resolve_working_directory(self, scope: str) -> Optional[Path]:
        scope_options = ('global', 'group', 'task')
        if scope not in scope_options:
            raise Exception(f'The given scope `{scope}` is not valid.')

        def update_working_directory(
            current_path: Union[None, Path], new_path: str
        ) -> Path:
            if not current_path:
                return Path(new_path)
            return current_path / Path(new_path)

        scope_id = scope_options.index(scope)

        working_dir: Optional[Path] = None

        if scope_id >= SCOPE_GLOBAL:
            working_dir = update_working_directory(
                working_dir, self.global_data.get('dir', '')
            )

        if scope_id >= SCOPE_GROUP:
            working_dir = update_working_directory(
                working_dir, self.group_data.get('dir', '')
            )

        if scope_id == SCOPE_TARGET:
            working_dir = update_working_directory(
                working_dir, self.task_data.get('dir', '')
            )

        return working_dir

    def _extract_shell_app_config(
        self, scoped_config: dict[str, Any]
    ) -> AppConfigType:
        """Extract the shell app configuration from the scoped config data."""
        shell_app_data: AppConfigType = scoped_config.get('backend', {})

        if not shell_app_data:
            return {}

        shell_app_default = DEFAULT_SHELL_NAME
        tmp_suffix_default = '.makim'

        shell_config: AppConfigType = {}

        if isinstance(shell_app_data, str):
            cmd = shell_app_data.split(' ')
            app_name = cmd[0]
            args: list[str] = KNOWN_SHELL_APP_ARGS.get(app_name, [])
            shell_config['app'] = cmd[0]
            shell_config['suffix'] = KNOWN_SHELL_APP_FILE_SUFFIX.get(
                app_name, tmp_suffix_default
            )
            shell_config['args'] = args + cmd[1:]
        elif isinstance(shell_app_data, dict):
            app_name = str(shell_app_data.get('app', shell_app_default))
            shell_config['app'] = app_name
            shell_tmp_suffix_default = KNOWN_SHELL_APP_FILE_SUFFIX.get(
                app_name, tmp_suffix_default
            )
            shell_config['suffix'] = shell_app_data.get(
                'suffix', shell_tmp_suffix_default
            )
            shell_config['args'] = shell_app_data.get('args', [])
        return shell_config

    def _load_shell_app(self) -> None:
        """Load the shell app."""
        shell_config: AppConfigType = {
            'app': DEFAULT_SHELL_NAME,
            'args': [],
            'suffix': '.makim',
        }
        tmp_suffix_default = '.makim'

        for scoped_data in [
            self.global_data,
            self.group_data,
            self.task_data,
        ]:
            tmp_config: AppConfigType = self._extract_shell_app_config(
                scoped_data
            )
            if tmp_config:
                shell_config = tmp_config

        cmd_name = str(shell_config.get('app', ''))
        cmd_args: list[str] = cast(List[str], shell_config.get('args', []))
        cmd_tmp_suffix: str = str(
            shell_config.get('suffix', tmp_suffix_default)
        )

        if not cmd_name:
            MakimLogs.raise_error(
                'The shell command is invalid',
                MakimError.MAKIM_CONFIG_FILE_INVALID,
            )

        self.shell_app = getattr(sh, cmd_name)
        self.shell_args = cmd_args
        self.tmp_suffix = cmd_tmp_suffix

    def _load_dotenv(self, data_scope: dict[str, Any]) -> dict[str, str]:
        env_file = data_scope.get('env-file')
        if not env_file:
            return {}

        if not env_file.startswith('/'):
            # use makim file as reference for the working directory
            # for the .env file
            env_file = str(Path(self.file).parent / env_file)

        if not Path(env_file).exists():
            MakimLogs.raise_error(
                'The given env-file was not found.',
                MakimError.MAKIM_ENV_FILE_NOT_FOUND,
            )

        env_vars = dotenv.dotenv_values(env_file)
        return {k: (v or '') for k, v in env_vars.items()}

    def _load_scoped_data(
        self, scope: str
    ) -> tuple[dict[str, str], dict[str, Any]]:
        scope_options = ('global', 'group', 'task')
        if scope not in scope_options:
            raise Exception(f'The given scope `{scope}` is not valid.')

        def _render_env_inplace(
            env_user: dict[str, Any],
            env_file: dict[str, Any],
            variables: dict[str, Any],
            env: dict[str, Any],
        ) -> None:
            env.update(env_file)
            for k, v in env_user.items():
                env[k] = TEMPLATE.from_string(str(v)).render(
                    env=env, vars=variables
                )

        scope_id = scope_options.index(scope)

        env = deepcopy(dict(os.environ))
        variables: dict[str, Any] = {}

        if scope_id >= SCOPE_GLOBAL:
            env_user = self.global_data.get('env', {})
            env_file = self._load_dotenv(self.global_data)
            _render_env_inplace(env_user, env_file, variables, env)
            variables.update(self._load_scoped_vars('global'))

        if scope_id >= SCOPE_GROUP:
            env_user = self.group_data.get('env', {})
            env_file = self._load_dotenv(self.group_data)
            _render_env_inplace(env_user, env_file, variables, env)
            variables.update(self._load_scoped_vars('group'))

        if scope_id == SCOPE_TARGET:
            env_user = self.task_data.get('env', {})
            env_file = self._load_dotenv(self.task_data)
            _render_env_inplace(env_user, env_file, variables, env)
            variables.update(self._load_scoped_vars('task'))

        return env, variables

    def _load_scoped_vars(self, scope: str) -> dict[str, Any]:
        scope_options = ('global', 'group', 'task')
        if scope not in scope_options:
            raise Exception(f'The given scope `{scope}` is not valid.')
        scope_id = scope_options.index(scope)

        variables = {}

        if scope_id >= SCOPE_GLOBAL:
            variables.update(
                {
                    k: strip_recursively(v)
                    for k, v in self.global_data.get('vars', {}).items()
                }
            )
        if scope_id >= SCOPE_GROUP:
            variables.update(
                {
                    k: strip_recursively(v)
                    for k, v in self.group_data.get('vars', {}).items()
                }
            )
        if scope_id == SCOPE_TARGET:
            variables.update(
                {
                    k: strip_recursively(v)
                    for k, v in self.task_data.get('vars', {}).items()
                }
            )

        return cast(Dict[str, Any], fix_dict_keys_recursively(variables))

    def _load_task_args(self) -> None:
        if self.args is None:
            self.args = {}
        for name, value in self.task_data.get('args', {}).items():
            qualified_name = f'--{name}'
            if qualified_name not in self.args:
                default = value.get('default')
                is_bool = value.get('type', '') == 'bool'
                self.args[qualified_name] = (
                    default
                    if default is not None
                    else (False if is_bool else None)
                )

    def _log_command_execution(
        self, execution_context: dict[str, Any], width: int
    ) -> None:
        """Log the command execution details.

        execution_context should contain: args_input, current_vars,
        env, and optionally matrix_vars
        """
        MakimLogs.print_info('=' * width)
        MakimLogs.print_info(
            'TARGET: ' + f'{self.group_name}.{self.task_name}'
        )
        MakimLogs.print_info('ARGS:')
        MakimLogs.print_info(pprint.pformat(execution_context['args_input']))
        MakimLogs.print_info('VARS:')
        MakimLogs.print_info(pprint.pformat(execution_context['current_vars']))
        MakimLogs.print_info('ENV:')
        MakimLogs.print_info(str(execution_context['env']))

        if execution_context.get('matrix_vars'):
            MakimLogs.print_info('MATRIX:')
            MakimLogs.print_info(
                pprint.pformat(execution_context['matrix_vars'])
            )

        MakimLogs.print_info('-' * width)

    def _generate_matrix_combinations(
        self, matrix_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Generate all possible combinations from matrix configuration.

        Parameters
        ----------
        matrix_config : dict
            Dictionary containing matrix variables and their possible values

        Returns
        -------
        list[dict]
            List of dictionaries, each containing one possible combination
        """
        if not matrix_config:
            return []

        # Convert matrix config into format suitable for product
        keys = list(matrix_config.keys())
        values = [
            matrix_config[k]
            if isinstance(matrix_config[k], list)
            else [matrix_config[k]]
            for k in keys
        ]

        combinations = []
        for combo in product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations

    # run commands
    def _run_hooks(self, args: dict[str, Any], hook_type: str) -> None:
        if not self.task_data.get('hooks', {}).get(hook_type):
            return
        makim_hook = deepcopy(self)
        args_hook_original = {
            'help': args.get('help', False),
            'version': args.get('version', False),
            'args': {},
        }

        makim_hook._change_group_data()

        # clean double dash prefix in args
        original_args_clean = {}
        for arg_name, arg_value in args.items():
            original_args_clean[
                arg_name.replace('--', '', 1).replace('-', '_')
            ] = (
                arg_value.replace('--', '', 1)
                if isinstance(arg_value, str)
                else arg_value
            )

        for hook_data in self.task_data['hooks'][hook_type]:
            env, variables = makim_hook._load_scoped_data('task')
            for k, v in env.items():
                os.environ[k] = v

            makim_hook.env_scoped = deepcopy(env)
            args_hook = {}

            # update the arguments
            for arg_name, arg_value in hook_data.get('args', {}).items():
                unescaped_value = str(arg_value)

                args_hook[f'--{arg_name}'] = yaml.safe_load(
                    TEMPLATE.from_string(unescaped_value).render(
                        args=original_args_clean, env=makim_hook.env_scoped
                    )
                )

            args_hook['task'] = hook_data['task']
            args_hook.update(args_hook_original)

            # checking for the conditional statement
            if_stmt = hook_data.get('if')
            if if_stmt:
                result = TEMPLATE.from_string(str(if_stmt)).render(
                    args=original_args_clean, env=self.env_scoped
                )
                if not yaml.safe_load(result):
                    if self.verbose:
                        MakimLogs.print_info(
                            f'[II] Skipping {hook_type} hook: '
                            f'{hook_data.get("task")}'
                        )
                    continue

            makim_hook.run(deepcopy(args_hook))

    def _run_command(self, args: dict[str, Any]) -> None:
        cmd = self.task_data.get('run', '').strip()
        remote_host = self.task_data.get('remote')

        if not isinstance(self.group_data.get('vars', {}), dict):
            MakimLogs.raise_error(
                '`vars` attribute inside the group '
                f'{self.group_name} is not a dictionary.',
                MakimError.MAKIM_VARS_ATTRIBUTE_INVALID,
            )

        # Get matrix configuration if it exists
        matrix_combinations: list[dict[str, Any]] = []
        if matrix_config := self.task_data.get('matrix', {}):
            matrix_combinations = self._generate_matrix_combinations(
                matrix_config
            )

        env, variables = self._load_scoped_data('task')
        self.env_scoped = deepcopy(env)

        args_input: dict[str, str | bool | float | int] = {'file': self.file}
        for k, v in self.task_data.get('args', {}).items():
            if not isinstance(v, dict):
                raise Exception('`args` attribute should be a dictionary.')
            k_clean = k.replace('-', '_')
            action = v.get('action', '').replace('-', '_')
            is_store_true = action == 'store_true'
            default = v.get('default', False if is_store_true else None)

            args_input[k_clean] = default

            input_flag = f'--{k}'
            if args.get(input_flag) is not None:
                if action == 'store_true':
                    args_input[k_clean] = (
                        True if args[input_flag] is None else args[input_flag]
                    )
                    continue

                args_input[k_clean] = (
                    args[input_flag].strip()
                    if isinstance(args[input_flag], str)
                    else args[input_flag]
                )
            elif v.get('required'):
                MakimLogs.raise_error(
                    f'The argument `{k}` is set as required. '
                    'Please, provide that argument to proceed.',
                    MakimError.MAKIM_ARGUMENT_REQUIRED,
                )

        width, _ = get_terminal_size()

        def process_matrix_combination(matrix_vars: dict[str, Any]) -> None:
            # Update environment variables
            for k, v in env.items():
                os.environ[k] = v

            # Create a copy of variables and update with matrix values
            current_vars = deepcopy(variables)
            if matrix_vars:
                current_vars['matrix'] = matrix_vars

            # Render command with current matrix values
            current_cmd = TEMPLATE.from_string(cmd).render(
                args=args_input, env=env, vars=current_vars, matrix=matrix_vars
            )

            if self.verbose:
                # Prepare execution context for logging
                execution_context = {
                    'args_input': args_input,
                    'current_vars': current_vars,
                    'env': env,
                    'matrix_vars': matrix_vars,
                }
                # Log command execution details
                self._log_command_execution(execution_context, width)
                MakimLogs.print_info(
                    '>>> ' + current_cmd.replace('\n', '\n>>> ')
                )
                MakimLogs.print_info('=' * width)

            if not self.dry_run and current_cmd:
                if remote_host:
                    host_config = self.ssh_config.get(remote_host)
                    if not host_config:
                        MakimLogs.raise_error(
                            f"""
                            Remote host '{remote_host}' configuration
                            not found.
                            """,
                            MakimError.REMOTE_HOST_NOT_FOUND,
                        )
                    self._call_shell_remote(
                        current_cmd, cast(dict[str, Any], host_config)
                    )
                else:
                    self._call_shell_app(current_cmd)

        # Run command for each matrix combination
        for matrix_vars in matrix_combinations or [{}]:
            process_matrix_combination(matrix_vars)

        # move back the environment variable to the previous values
        os.environ.clear()
        os.environ.update(self.env_scoped)

    # public methods
    def load(
        self, file: str, dry_run: bool = False, verbose: bool = False
    ) -> None:
        """Load makim configuration."""
        self.file = file
        self.dry_run = dry_run
        self.verbose = verbose

        self._load_config_data()
        self._verify_config()
        self.env = self._load_dotenv(self.global_data)

    def run(self, args: dict[str, Any]) -> None:
        """Run makim task code."""
        self.args = args

        # setup
        self._verify_args()
        self._change_task(args['task'])
        self._load_task_args()

        # commands
        if self.task_data.get('if') and not self._verify_task_conditional(
            self.task_data['if']
        ):
            return warnings.warn(
                f'{args["task"]} not executed. Condition (if) not satisfied.'
            )

        self._run_hooks(args, 'pre-run')
        self._run_command(args)
        self._run_hooks(args, 'post-run')
