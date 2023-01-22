import argparse
import os
from pathlib import Path

from makim import Makim, __version__


def _get_args():
    parser = argparse.ArgumentParser(
        prog='MakIm',
        description=(
            'MakIm is a tool that help you to organize'
            "and simplify your helper commands"
        ),
        epilog=(
            'If you have any problem, open an issue at: '
            'https://github.com/osl-incubator/makim'
        ),
    )

    parser.add_argument(
        'target',
        help=(
            'Specify the command to be performed. '
            'If you have more than one group in your .makim.yaml file, '
            'you need to specify the group too, for example: '
            '"my-group:my-target".'
        ),
    )
    parser.add_argument(
        '--args',
        type=str,
        help=(
            'Set the arguments for the call. '
            "Use comma to separate the arguments"
        ),
    )
    parser.add_argument(
        '--config-file',
        type=str,
        default=str(Path(os.getcwd()) / '.makim.yaml'),
        help='Specify a custom location for the config file.',
    )
    return parser


def show_version():
    print(__version__)


def app():
    args_parser = _get_args()
    args = args_parser.parse_args()

    if args.target == 'help':
        return args_parser.print_help()

    if args.target == 'version':
        return show_version()

    makim = Makim(args)
    return makim.run()


if __name__ == '__main__':
    app()
