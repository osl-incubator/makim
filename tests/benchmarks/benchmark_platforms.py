"""Benchmark different platform implementations in Makim."""

import platform
import subprocess
import time


def run_command(cmd, shell=True):
    """Run a command and measure its execution time.

    Parameters
    ----------
    cmd : str
        The command to run
    shell : bool, default True
        Whether to run the command in a shell

    Returns
    -------
    dict
        Dictionary with execution time and success status
    """
    start_time = time.time()
    process = subprocess.run(
        cmd, shell=shell, capture_output=True, text=True, check=False
    )
    end_time = time.time()
    return {
        'time': end_time - start_time,
        'success': process.returncode == 0,
        'output': process.stdout,
        'error': process.stderr,
        'returncode': process.returncode,
    }


def main():
    """Run benchmarks for different command."""
    print(f'Running benchmarks on {platform.system()} {platform.release()}')
    print(f'Python version: {platform.python_version()}')

    # Commands to test on each platform
    commands = []

    if platform.system() == 'Windows':
        commands = [
            ('Windows CMD echo', 'echo Hello World'),
            (
                'Windows PowerShell',
                'powershell -Command "Write-Host \'Hello World\'"',
            ),
            ('Windows dir command', 'dir'),
        ]
    else:
        commands = [
            ('Unix echo', 'echo Hello World'),
            ('Unix ls command', 'ls -la'),
            ('Unix pwd command', 'pwd'),
        ]

    # Common Python commands for all platforms
    common_commands = [
        ('Python subprocess', 'python -c "print(\'Hello World\')"'),
        ('Python version command', 'python --version'),
    ]

    commands.extend(common_commands)

    results = []

    for desc, cmd in commands:
        print(f'Running: {desc}')
        result = run_command(cmd)
        results.append((desc, result))

    print('\nBenchmark Results:')
    print('-' * 50)

    for desc, result in results:
        status_mark = '✓' if result['success'] else '✗'
        print(f'{desc.ljust(30)} {result["time"]:.4f}s {status_mark}')


if __name__ == '__main__':
    main()
