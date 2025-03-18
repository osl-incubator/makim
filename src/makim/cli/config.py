"""Cli functions to define the arguments and to call Makim."""

from __future__ import annotations

import sys

import typer

CLI_ROOT_FLAGS_VALUES_COUNT = {
    '--dry-run': 0,
    '--file': 1,
    '--help': 0,  # not necessary to store this value
    '--verbose': 0,
    '--version': 0,  # not necessary to store this value
    '--skip-hooks': 0,
}


def extract_root_config(
    cli_list: list[str] = sys.argv,
) -> dict[str, str | bool]:
    """Extract the root configuration from the CLI."""
    params = cli_list[1:]

    # default values
    makim_file = '.makim.yaml'
    dry_run = False
    verbose = False
    skip_hooks = False

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
            elif arg == '--skip-hooks':
                skip_hooks = True

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
        'skip_hooks': skip_hooks,
    }
