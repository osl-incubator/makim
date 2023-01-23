import argparse
import os
from pathlib import Path

import yaml

from makim import Makim, __version__


class CustomHelpFormatter(argparse.RawTextHelpFormatter):
    """Formatter for generating usage messages and argument help strings.

    Only the name of this class is considered a public API. All the methods
    provided by the class are considered an implementation detail.
    """

    def __init__(
        self,
        prog,
        indent_increment=2,
        max_help_position=4,
        width=None,
        **kwargs,
    ):
        super().__init__(
            prog,
            indent_increment=indent_increment,
            max_help_position=max_help_position,
            width=width,
            **kwargs,
        )


makim = Makim()


def _get_args():
    parser = argparse.ArgumentParser(
        prog='MakIm',
        description=(
            'MakIm is a tool that helps you to organize '
            'and simplify your helper commands.'
        ),
        epilog=(
            'If you have any problem, open an issue at: '
            'https://github.com/osl-incubator/makim'
        ),
        add_help=False,
        formatter_class=CustomHelpFormatter,
    )

    parser.add_argument(
        '--help',
        '-h',
        action='store_true',
        help='Show the help menu',
    )

    parser.add_argument(
        '--version',
        action='store_true',
        help='Show the version of the installed MakIm tool.',
    )

    parser.add_argument(
        '--config-file',
        type=str,
        default=str(Path(os.getcwd()) / '.makim.yaml'),
        help='Specify a custom location for the config file.',
    )

    args = parser.parse_args([])

    makim.load(args.config_file)

    target_help = []

    for group in makim.config_data['groups']:
        for target_name, target_data in group['targets'].items():
            target_name_qualified = f"{group['name']}.{target_name}"
            help_text = target_data['help'] if 'help' in target_data else ''

            target_help.append(f'  {target_name_qualified} => {help_text}')

            if 'args' in target_data:
                target_help.append(f'    ARGS:')

                for arg_name, arg_data in target_data['args'].items():
                    target_help.append(
                        f'      --{arg_name}: ({arg_data["type"]}) {arg_data["help"]}'
                    )

    target_help.append("NOTE: 'default.' prefix is optional.")

    parser.add_argument(
        'target',
        nargs='?',
        default=None,
        help=(
            'Specify the target command to be performed. '
            '\nOptions are:\n' + '\n'.join(target_help)
        ),
    )

    return parser


def show_version():
    print(__version__)


def app():
    args_parser = _get_args()
    args = args_parser.parse_args()

    if args.help:
        return args_parser.print_help()

    if args.version:
        return show_version()

    return makim.run(dict(args._get_kwargs()))


if __name__ == '__main__':
    app()
