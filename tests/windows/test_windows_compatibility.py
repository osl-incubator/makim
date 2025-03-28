"""Tests for Windows compatibility features in Makim."""

import os
import platform

import pytest


def test_platform_detection():
    """Test platform detection functions for different environments."""
    from makim.core import is_windows, is_wsl

    # Check platform detection
    if platform.system() == 'Windows':
        assert is_windows()
        assert not is_wsl()
    elif 'WSL_DISTRO_NAME' in os.environ or (
        platform.system() == 'Linux'
        and os.path.exists('/proc/version')
        and 'microsoft' in open('/proc/version').read().lower()
    ):
        assert not is_windows()
        assert is_wsl()
    else:
        assert not is_windows()
        assert not is_wsl()


def test_subprocess_execution():
    """Test cross-platform subprocess execution."""
    from makim.core import ShellCommand

    # Create a simple echo command
    echo_command = ShellCommand(
        'echo' if platform.system() != 'Windows' else 'cmd'
    )

    # Test execution
    if platform.system() == 'Windows':
        process = echo_command('/c', 'echo', 'Hello World', _bg=True)
    else:
        process = echo_command('Hello World', _bg=True)

    # Wait for completion
    exit_code = process.wait()

    # Process should complete successfully
    assert exit_code == 0


@pytest.mark.skipif(
    platform.system() != 'Windows', reason='Windows-specific test'
)
def test_powershell_execution():
    """Test PowerShell command execution on Windows."""
    from makim.core import ShellCommand

    # Create PowerShell command
    powershell = ShellCommand('powershell')

    # Execute a simple PowerShell command
    process = powershell(
        '-Command', 'Write-Output "Hello from PowerShell"', _bg=True
    )

    # Wait for completion
    exit_code = process.wait()

    # Should complete successfully
    assert exit_code == 0


@pytest.mark.skipif(
    platform.system() != 'Windows', reason='Windows-specific test'
)
def test_path_handling():
    """Test path normalization on Windows platforms."""
    from makim.core import _normalize_path

    # Test Windows path normalization
    unix_path = '/some/unix/path'
    normalized = _normalize_path(unix_path)

    # Should convert to Windows path format
    assert '\\' in normalized
    assert normalized == os.path.normpath(unix_path)
