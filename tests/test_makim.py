"""Tests for `makim` package."""
from pathlib import Path

import pytest

import makim


@pytest.mark.parametrize(
    'args',
    [
        {'target': 'tests.test-1'},
        {'target': 'tests.test-1', '--all': False},
        {'target': 'tests.test-2', '--all': True},
        {'target': 'tests.test-3-a'},
        {'target': 'tests.test-3-b'},
        {'target': 'tests.test-4'},
        {'target': 'tests.test-4', '--trigger-dep': True},
    ],
)
def test_success(args):
    makim_file = Path(__file__).parent / '.makim-unittest.yaml'

    m = makim.Makim()
    m.load(makim_file)

    args.update({'makim_file': makim_file})

    m.run(args)
