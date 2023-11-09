"""Tests for `makim` package."""
import os
import sys

from pathlib import Path

import pytest

import makim

from makim.errors import MakimError


@pytest.mark.parametrize(
    'target,args,error_code',
    [
        ('tests.test-7', {}, MakimError.MAKIM_ARGUMENT_REQUIRED.value),
        ('tests.test-8', {}, MakimError.SH_ERROR_RETURN_CODE.value),
        ('tests.test-9', {}, MakimError.SH_ERROR_RETURN_CODE.value),
    ],
)
def test_failure(target, args, error_code):
    """Test makim with expected failures."""
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
    assert pytest_wrapped_e.value.code == error_code
