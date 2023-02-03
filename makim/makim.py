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
    args: Optional[object] = None
    makim_file: str = '.makim.yaml'
    config_data: dict = {}
    shell_app: Optional[object] = None
    shell_args: list = []
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

    def _load_group_target_name(self):
        if '.' in self.args['target']:
            self.group_name, self.target_name = self.args['target'].split('.')
            return
        self.group_name = 'default'
        self.target_name = self.args['target']

    def _load_target_data(self):
        self.target_data = self.group_data['targets'][self.target_name]

    def _load_shell_app(self):
        self.shell_app = shell_app

    def _filter_group_data(self, group_name=None):
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
        self._filter_group_data()
        self.shell_args = ['-c']

    # run commands

    def _run_dependencies(self, args: dict):
        if (
            'dependencies' not in self.target_data
            or not self.target_data['dependencies']
        ):
            return

        makim_dep = deepcopy(self)
        args_dep = deepcopy(args)

        makim_dep._filter_group_data()

        for dep_data in self.target_data['dependencies']:
            args_dep['target'] = dep_data['target']
            makim_dep.run(args_dep)

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
            args_input[k] = (
                None if 'default' not in v else None
            )   # v["default"]

            input_flag = f'--{k}'
            if input_flag in args:
                args_input[k] = (
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
        self._load_group_target_name()
        self._load_shell_args()
        self._load_target_data()

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
