"""Makim class for containers"""
import io
import os
import sys
import warnings
from copy import deepcopy
from pathlib import Path
from typing import Optional

from jinja2 import Template

import sh
import yaml

from sh import xonsh as shell_app


class Makim:
    makim_file: str = '.makim.yaml'
    config_data: dict = {}
    shell_app: Optional[object] = None
    shell_args: list = []

    # temporary variables
    args: Optional[object] = None
    group_name: str = 'default'
    group_data: dict = {}
    target_name: str = ''
    target_data: dict = {}

    def _call_shell_app(self, *args):
        p = self.shell_app(
            *self.shell_args,
            args,
            _out=sys.stdout,
            _err=sys.stderr,
            _bg=True,
            _bg_exc=False,
            _no_err=True,
            _env=os.environ,
        )

        try:
            p.wait()
        except sh.ErrorReturnCode:
            ...
        except KeyboardInterrupt:
            pid = p.pid
            p.kill()
            print(f'[WW] Process {pid} killed.')

    def _check_makim_file(self):
        return Path(self.makim_file).exists()

    def _verify_target_conditional(self, conditional):
        ...

    def _verify_args(self):
        if not self._check_makim_file():
            raise Exception('[config] Config file .makim.yaml not found.')

    def _verify_config(self):
        if not len(self.config_data['groups']):
            raise Exception('No target groups found.')

    def _load_config_data(self):
        with open(self.makim_file, 'r') as f:
            # escape template tags
            content = f.read().replace('{{', '\{\{').replace('}}', '\}\}')
            f = io.StringIO(content)
            self.config_data = yaml.safe_load(f)

    def _load_shell_app(self):
        self.shell_app = shell_app

    def _change_target(self, target_name: str):
        group_name = 'default'
        if '.' in target_name:
            group_name, target_name = target_name.split('.')

        self.target_name = target_name
        self._change_group_data(group_name)

        for target_name, target_data in self.group_data['targets'].items():
            if target_name == self.target_name:
                self.target_data = target_data
                return

        print(
            f'[EE] The given target "{self.target_name}" was not found in the '
            f'configuration file for the group {self.group_name}.'
        )
        exit(1)

    def _change_group_data(self, group_name=None):
        groups = self.config_data['groups']

        if group_name is not None:
            self.group_name = group_name

        if self.group_name == 'default' and len(groups) == 1:
            self.group_data = groups[0]
            self.group_name = groups[0]['name']
            return

        for g in groups:
            if g['name'] == self.group_name:
                self.group_data = g
                return

        raise Exception(
            f'The given group target "{self.group_name}" was not found in the '
            'configuration file.'
        )

    def _load_shell_args(self):
        self._change_group_data()
        self.shell_args = ['-c']

    # run commands

    def _run_dependencies(self, args: dict):
        if (
            'dependencies' not in self.target_data
            or not self.target_data['dependencies']
        ):
            return

        makim_dep = deepcopy(self)
        args_dep = {
            'makim_file': args['makim_file'],
            'help': args['help'],
            'verbose': args['verbose'],
            'version': args['version'],
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
            args_dep['args'] = {}

            # check conditional

            # update the arguments
            for arg_name, arg_value in dep_data.get('args', {}).items():
                unescaped_value = arg_value.replace('\{\{', '{{').replace(
                    '\}\}', '}}'
                )
                args_dep[f'--{arg_name}'] = Template(unescaped_value).render(
                    args=original_args_clean
                )

            args_dep['target'] = dep_data['target']
            makim_dep.run(deepcopy(args_dep))

    def _run_command(self, args: dict):
        cmd = self.target_data['run'].strip()

        if not 'vars' in self.group_data:
            self.group_data['vars'] = {}

        if not isinstance(self.group_data['vars'], dict):
            print(
                '[EE] `vars` attribute inside the group '
                f'{self.group_name} is not a dictionary.'
            )
            exit(1)

        variables = {k: v.strip() for k, v in self.group_data['vars'].items()}

        args_input = {}
        for k, v in self.target_data.get('args', {}).items():
            k_clean = k.replace('-', '_')
            args_input[k_clean] = v.get(
                'default', False if v.get('actions') == 'store_true' else None
            )

            input_flag = f'--{k}'
            if input_flag in args:
                if v.get('actions') == 'store_true':
                    args_input[k_clean] = True
                    continue

                args_input[k_clean] = (
                    args[input_flag].strip()
                    if isinstance(args[input_flag], str)
                    else args[input_flag]
                )

        # revert template tags escape
        cmd = cmd.replace('\{\{', '{{').replace('\}\}', '}}')
        cmd = Template(cmd).render(args=args_input, **variables)
        if args.get('verbose'):
            print('-' * 80)
            print('>>>', cmd.replace('\n', '\n>>> '))
            print('-' * 80)
        self._call_shell_app(cmd)

    # public methods

    def load(self, makim_file: str):
        self.makim_file = makim_file
        self._load_config_data()
        self._verify_config()
        self._load_shell_app()

    def run(self, args: dict):
        self.args = args

        # setup
        self._verify_args()
        self._change_target(args['target'])
        self._load_shell_args()

        # commands
        if 'if' in self.target_data and not self._verify_target_conditional(
            self.target_data['if']
        ):
            return warnings.warn(
                f'{args["target"]} not executed. '
                'Condition (if) not satisfied.'
            )

        self._run_dependencies(args)
        self._run_command(args)
