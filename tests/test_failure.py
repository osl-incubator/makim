"""Tests for `makim` package."""
import os
import sys
from pathlib import Path

import pytest

import makim


@pytest.mark.parametrize(
    'target,args',
    [
        ('tests.test-7', {}),
    ],
)
def test_failure(target, args):
    makim_file = Path(__file__).parent / '.makim-unittest.yaml'

    m = makim.Makim()
    m.load(makim_file)

    args.update(
        {
            'target': target,
            'makim_file': makim_file,
        }
    )
    # mock the exit function used by makim
    os._exit = sys.exit
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        m.run(args)
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
