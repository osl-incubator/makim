"""Makim class for containers"""
import io
import os
import sys
import tempfile
import warnings
from copy import deepcopy
from pathlib import Path
from pprint import pprint
from typing import Optional

import dotenv
import sh
import yaml
from colorama import Fore
from jinja2 import Template


def escape_template_tag(v: str) -> str:
    return v.replace('{{', r'\{\{').replace('}}', r'\}\}')


def unescape_template_tag(v: str) -> str:
    return v.replace(r'\{\{', '{{').replace(r'\}\}', '}}')


class PrintPlugin:
    def _print_error(self, message: str):
        print(Fore.RED, message, Fore.RESET)

    def _print_info(self, message: str):
        print(Fore.BLUE, message, Fore.RESET)

    def _print_warning(self, message: str):
        print(Fore.YELLOW, message, Fore.RESET)


class Makim(PrintPlugin):
    makim_file: str = '.makim.yaml'
    config_data: dict = {}
    shell_app: sh.Command = sh.xonsh

    # temporary variables
    env: dict = {}
    args: Optional[object] = None
    group_name: str = 'default'
    group_data: dict = {}
    target_name: str = ''
    target_data: dict = {}

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
        )

        try:
            p.wait()
        except sh.ErrorReturnCode as e:
            os.close(fd)
            self._print_error(str(e))
            os._exit(1)
        except KeyboardInterrupt:
            os.close(fd)
            pid = p.pid
            p.kill_group()
            self._print_error(f'[EE] Process {pid} killed.')
            os._exit(1)
        os.close(fd)

    def _check_makim_file(self):
        return Path(self.makim_file).exists()

    def _verify_target_conditional(self, conditional):
        ...

    def _verify_args(self):
        if not self._check_makim_file():
            self._print_error(
                '[EE] CONFIG: Config file .makim.yaml not found.'
            )
            os._exit(1)

    def _verify_config(self):
        if not len(self.config_data['groups']):
            self._print_error('[EE] No target groups found.')
            os._exit(1)

    def _load_config_data(self):
        with open(self.makim_file, 'r') as f:
            # escape template tags
            content = escape_template_tag(f.read())
            f = io.StringIO(content)
            self.config_data = yaml.safe_load(f)

    def _load_shell_app(self, shell_app: str = ''):
        if not shell_app:
            shell_app = self.config_data.get('shell', 'xonsh')
        self.shell_app = getattr(sh, shell_app)

    def _change_target(self, target_name: str):
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

        self._print_error(
            f'[EE] The given target "{self.target_name}" was not found in the '
            f'configuration file for the group {self.group_name}.'
        )
        os._exit(1)

    def _change_group_data(self, group_name=None):
        groups = self.config_data['groups']

        if group_name is not None:
            self.group_name = group_name
        shell_app_default = self.config_data.get('shell', 'xonsh')
        if self.group_name == 'default' and len(groups) == 1:
            group = list(groups)[0]
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

        self._print_error(
            f'[EE] The given group target "{self.group_name}" '
            'was not found in the configuration file.'
        )
        os._exit(1)

    @property
    def shell_args(self):
        if self.shell_app.__dict__['__name__'].endswith('bash'):
            return ['-e']
        return []

    # run commands

    def _run_dependencies(self, args: dict):
        if not self.target_data.get('dependencies'):
            return
        makim_dep = deepcopy(self)
        args_dep_original = {
            'makim_file': args['makim_file'],
            'help': args.get('help', False),
            'verbose': args.get('verbose', False),
            'dry-run': args.get('dry-run', False),
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
            args_dep = {}

            # update the arguments
            for arg_name, arg_value in dep_data.get('args', {}).items():
                unescaped_value = (
                    unescape_template_tag(arg_value)
                    if isinstance(arg_value, str)
                    else str(arg_value)
                )

                args_dep[f'--{arg_name}'] = yaml.safe_load(
                    Template(unescaped_value).render(args=original_args_clean)
                )

            args_dep['target'] = dep_data['target']
            args_dep.update(args_dep_original)

            # checking for the conditional statement
            if_stmt = dep_data.get('if')
            if if_stmt:
                result = Template(unescape_template_tag(if_stmt)).render(
                    args=original_args_clean
                )
                if not yaml.safe_load(result):
                    if args.get('verbose'):
                        self._print_info(
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
            self._print_error(
                '[EE] `vars` attribute inside the group '
                f'{self.group_name} is not a dictionary.'
            )
            os._exit(1)

        variables = {k: v.strip() for k, v in self.group_data['vars'].items()}

        args_input = {'makim_file': args['makim_file']}
        for k, v in self.target_data.get('args', {}).items():
            k_clean = k.replace('-', '_')
            action = v.get('action', '').replace('-', '_')
            is_store_true = action == 'store_true'
            default = v.get('default', False if is_store_true else None)

            args_input[k_clean] = default

            input_flag = f'--{k}'
            if input_flag in args and args[input_flag]:
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
                self._print_error(
                    f'[EE] The argument `{k}` is set as required. '
                    'Please, provide that argument to proceed.'
                )
                os._exit(1)

        current_env = deepcopy(os.environ)
        env = deepcopy(self.env)
        for k, v in self.target_data.get('env', {}).items():
            env[k] = Template(unescape_template_tag(v)).render(
                args=args_input, **variables
            )
        for k, v in env.items():
            os.environ[k] = v

        cmd = unescape_template_tag(cmd)
        cmd = Template(cmd).render(args=args_input, **variables)
        if args.get('verbose'):
            print('=' * 80)
            print('TARGET:', f'{self.group_name}.{self.target_name}')
            print('ARGS:')
            pprint(args_input)
            print('VARS:')
            pprint(variables)
            print('ENV:')
            pprint(env)
            print('-' * 80)
            print('>>>', cmd.replace('\n', '\n>>> '))
            print('=' * 80)

        if not args.get('dry_run') and cmd:
            self._call_shell_app(cmd)

        # move back the environment variable to the previous values
        os.environ.clear()
        os.environ.update(current_env)

    def _load_dotenv(self):
        env_file = self.config_data.get('env-file')
        if not env_file:
            return

        if not env_file.startswith('/'):
            # use makim file as reference for the working directory
            # for the .env file
            env_file = str(Path(self.makim_file).parent / env_file)

        if not Path(env_file).exists():
            self._print_error('[EE] The given env-file was not found.')
            os._exit(1)

        self.env = dotenv.dotenv_values(env_file)

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

    # public methods

    def load(self, makim_file: str):
        self.makim_file = makim_file
        self._load_config_data()
        self._verify_config()
        self._load_shell_app()
        self._load_dotenv()

    def run(self, args: dict):
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
