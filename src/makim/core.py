"""
Makim main class.

`Makim` or just `makim` is based on `make` and focus on improve
the way to define targets and dependencies. Instead of using the
`Makefile` format, it uses `yaml` format.
"""
from __future__ import annotations

import copy
import io
import os
import pprint
import sys
import tempfile
import warnings

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional, Union

import dotenv
import sh
import yaml  # type: ignore

from jinja2 import Template

from makim.console import get_terminal_size
from makim.logs import MakimError, MakimLogs

SCOPE_GLOBAL = 0
SCOPE_GROUP = 1
SCOPE_TARGET = 2


KNOWN_SHELL_APP_ARGS = {
    'bash': ['-e'],
    'php': ['-f'],
}


def escape_template_tag(v: str) -> str:
    """Escape template tag when processing the template config file."""
    return v.replace('{{', r'\{\{').replace('}}', r'\}\}')


def unescape_template_tag(v: str) -> str:
    """Unescape template tag when processing the template config file."""
    return v.replace(r'\{\{', '{{').replace(r'\}\}', '}}')


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
    global_data: dict = {}
    shell_app: sh.Command = sh.xonsh
    shell_args: list[str] = []

    # temporary variables
    env: dict = {}  # initial env
    env_scoped: dict = {}  # current env
    # initial working directory
    working_directory: Optional[Path] = None
    # current working directory
    working_directory_scoped: Optional[Path] = None
    args: Optional[object] = None
    group_name: str = 'default'
    group_data: dict = {}
    target_name: str = ''
    target_data: dict = {}

    def __init__(self):
        """Prepare the Makim class with the default configuration."""
        os.environ['RAISE_SUBPROC_ERROR'] = '1'
        os.environ['XONSH_SHOW_TRACEBACK'] = '0'

        # default
        self.file = '.makim.yaml'
        self.dry_run = False
        self.verbose = False
        self.shell_args: list[str] = []

    def _call_shell_app(self, cmd):
        fd, filepath = tempfile.mkstemp(suffix='.makim', text=True)

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
            _cwd=str(self._resolve_working_directory('target')),
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

    def _check_makim_file(self, file_path: str = '') -> bool:
        return Path(file_path or self.file).exists()

    def _verify_target_conditional(self, conditional) -> bool:
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
                'No target groups found.',
                MakimError.MAKIM_NO_TARGET_GROUPS_FOUND,
            )

    def _change_target(self, target_name: str) -> None:
        group_name = 'default'
        if '.' in target_name:
            group_name, target_name = target_name.split('.')

        self.target_name = target_name
        self._change_group_data(group_name)

        for target_name, target_data in self.group_data['targets'].items():
            if target_name == self.target_name:
                self.target_data = target_data
                shell_app = target_data.get('shell')
                if shell_app:
                    self._load_shell_app(shell_app)
                return

        MakimLogs.raise_error(
            f'The given target "{self.target_name}" was not found in the '
            f'configuration file for the group {self.group_name}.',
            MakimError.MAKIM_TARGET_NOT_FOUND,
        )

    def _change_group_data(self, group_name=None) -> None:
        groups = self.global_data['groups']

        if group_name is not None:
            self.group_name = group_name
        shell_app_default = self.global_data.get('shell', 'xonsh')
        if self.group_name == 'default' and len(groups) == 1:
            group = next(iter(groups))
            self.group_data = groups[group]

            shell_app = self.group_data.get('shell', shell_app_default)
            self._load_shell_app(shell_app)
            return

        for group in groups:
            if group == self.group_name:
                self.group_data = groups[group]
                shell_app = groups[group].get('shell', shell_app_default)
                self._load_shell_app(shell_app)
                return

        MakimLogs.raise_error(
            f'The given group target "{self.group_name}" '
            'was not found in the configuration file.',
            MakimError.MAKIM_GROUP_NOT_FOUND,
        )

    def _load_config_data(self) -> None:
        if not self._check_makim_file():
            MakimLogs.raise_error(
                f'Makim file {self.file} not found',
                MakimError.MAKIM_CONFIG_FILE_NOT_FOUND,
            )

        with open(self.file, 'r') as f:
            # escape template tags
            content = escape_template_tag(f.read())
            content_io = io.StringIO(content)
            self.global_data = yaml.safe_load(content_io)

    def _resolve_working_directory(self, scope: str) -> Optional[Path]:
        scope_options = ('global', 'group', 'target')
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
                working_dir, self.global_data.get('working-directory', '')
            )

        if scope_id >= SCOPE_GROUP:
            working_dir = update_working_directory(
                working_dir, self.group_data.get('working-directory', '')
            )

        if scope_id == SCOPE_TARGET:
            working_dir = update_working_directory(
                working_dir, self.target_data.get('working-directory', '')
            )

        return working_dir

    def _load_shell_app(self, shell_app: str = '') -> None:
        if not shell_app:
            shell_app = self.global_data.get('shell', 'xonsh')
            return

        cmd = shell_app.split(' ')
        cmd_name = cmd[0]
        self.shell_app = getattr(sh, cmd_name)

        args: list[str] = KNOWN_SHELL_APP_ARGS.get(cmd_name, [])
        self.shell_args = args + cmd[1:]

    def _load_dotenv(self, data_scope: dict) -> dict[str, str]:
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
    ) -> tuple[dict[str, str], dict[str, str]]:
        scope_options = ('global', 'group', 'target')
        if scope not in scope_options:
            raise Exception(f'The given scope `{scope}` is not valid.')

        def _render_env_inplace(
            env_user: dict, env_file: dict, variables: dict, env: dict
        ):
            env.update(env_file)
            for k, v in env_user.items():
                env[k] = Template(unescape_template_tag(str(v))).render(
                    env=env, vars=variables
                )

        scope_id = scope_options.index(scope)

        env = deepcopy(dict(os.environ))
        variables: dict = {}

        if scope_id >= SCOPE_GLOBAL:
            env_user = self.global_data.get('env', {})
            env_file = self._load_dotenv(self.global_data)
            _render_env_inplace(env_user, env_file, variables, env)
            variables.update(self._load_scoped_vars('global', env=env))

        if scope_id >= SCOPE_GROUP:
            env_user = self.group_data.get('env', {})
            env_file = self._load_dotenv(self.group_data)
            _render_env_inplace(env_user, env_file, variables, env)
            variables.update(self._load_scoped_vars('group', env=env))

        if scope_id == SCOPE_TARGET:
            env_user = self.target_data.get('env', {})
            env_file = self._load_dotenv(self.target_data)
            _render_env_inplace(env_user, env_file, variables, env)
            variables.update(self._load_scoped_vars('target', env=env))

        return env, variables

    def _load_scoped_vars(self, scope: str, env) -> dict:
        scope_options = ('global', 'group', 'target')
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
                    for k, v in self.target_data.get('vars', {}).items()
                }
            )

        return fix_dict_keys_recursively(variables)

    def _load_target_args(self):
        for name, value in self.target_data.get('args', {}).items():
            qualified_name = f'--{name}'
            if self.args.get(qualified_name):
                continue
            default = value.get('default')
            is_bool = value.get('type', '') == 'bool'
            self.args[qualified_name] = (
                default if default is not None else False if is_bool else None
            )

    # run commands

    def _run_dependencies(self, args: dict):
        if not self.target_data.get('dependencies'):
            return
        makim_dep = deepcopy(self)
        args_dep_original = {
            'help': args.get('help', False),
            'version': args.get('version', False),
            'args': {},
        }

        makim_dep._change_group_data()

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

        for dep_data in self.target_data['dependencies']:
            env, variables = makim_dep._load_scoped_data('target')
            for k, v in env.items():
                os.environ[k] = v

            makim_dep.env_scoped = deepcopy(env)
            args_dep = {}

            # update the arguments
            for arg_name, arg_value in dep_data.get('args', {}).items():
                unescaped_value = (
                    unescape_template_tag(str(arg_value))
                    if isinstance(arg_value, str)
                    else str(arg_value)
                )

                args_dep[f'--{arg_name}'] = yaml.safe_load(
                    Template(unescaped_value).render(
                        args=original_args_clean, env=makim_dep.env_scoped
                    )
                )

            args_dep['target'] = dep_data['target']
            args_dep.update(args_dep_original)

            # checking for the conditional statement
            if_stmt = dep_data.get('if')
            if if_stmt:
                result = Template(unescape_template_tag(str(if_stmt))).render(
                    args=original_args_clean, env=self.env_scoped
                )
                if not yaml.safe_load(result):
                    if self.verbose:
                        MakimLogs.print_info(
                            '[II] Skipping dependency: '
                            f'{dep_data.get("target")}'
                        )
                    continue

            makim_dep.run(deepcopy(args_dep))

    def _run_command(self, args: dict):
        cmd = self.target_data.get('run', '').strip()
        if 'vars' not in self.group_data:
            self.group_data['vars'] = {}

        if not isinstance(self.group_data['vars'], dict):
            MakimLogs.raise_error(
                '`vars` attribute inside the group '
                f'{self.group_name} is not a dictionary.',
                MakimError.MAKIM_VARS_ATTRIBUTE_INVALID,
            )

        env, variables = self._load_scoped_data('target')
        for k, v in env.items():
            os.environ[k] = v

        self.env_scoped = deepcopy(env)

        args_input = {'file': self.file}
        for k, v in self.target_data.get('args', {}).items():
            if not isinstance(v, dict):
                raise Exception('`args` attribute should be a dictionary.')
            k_clean = k.replace('-', '_')
            action = v.get('action', '').replace('-', '_')
            is_store_true = action == 'store_true'
            default = v.get('default', False if is_store_true else None)

            args_input[k_clean] = default

            input_flag = f'--{k}'
            if args.get(input_flag):
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

        cmd = unescape_template_tag(str(cmd))
        cmd = Template(cmd).render(args=args_input, env=env, vars=variables)
        width, _ = get_terminal_size()

        if self.verbose:
            MakimLogs.print_info('=' * width)
            MakimLogs.print_info(
                'TARGET: ' + f'{self.group_name}.{self.target_name}'
            )
            MakimLogs.print_info('ARGS:')
            MakimLogs.print_info(pprint.pformat(args_input))
            MakimLogs.print_info('VARS:')
            MakimLogs.print_info(pprint.pformat(variables))
            MakimLogs.print_info('ENV:')
            MakimLogs.print_info(str(env))
            MakimLogs.print_info('-' * width)
            MakimLogs.print_info('>>> ' + cmd.replace('\n', '\n>>> '))
            MakimLogs.print_info('=' * width)

        if not self.dry_run and cmd:
            self._call_shell_app(cmd)

        # move back the environment variable to the previous values
        os.environ.clear()
        os.environ.update(self.env_scoped)

    # public methods

    def load(self, file: str, dry_run: bool = False, verbose: bool = False):
        """Load makim configuration."""
        self.file = file
        self.dry_run = dry_run
        self.verbose = verbose

        self._load_config_data()
        self._verify_config()
        self._load_shell_app()
        self.env = self._load_dotenv(self.global_data)

    def run(self, args: dict):
        """Run makim target code."""
        self.args = args

        # setup
        self._verify_args()
        self._change_target(args['target'])
        self._load_target_args()

        # commands
        if self.target_data.get('if') and not self._verify_target_conditional(
            self.target_data['if']
        ):
            return warnings.warn(
                f'{args["target"]} not executed. '
                'Condition (if) not satisfied.'
            )

        self._run_dependencies(args)
        self._run_command(args)
