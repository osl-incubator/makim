# Makim Configuration Specification

This document provides a comprehensive specification for the Makim configuration
file (`.makim.yaml`), detailing the structure, groups, tasks, and their
functionalities.

## Overview

The `.makim.yaml` file defines task groups and their associated tasks. Each task
specifies a command to be executed, often using Bash or other tools. It includes
groups for cleaning temporary files, building documentation, releasing software,
running tests, and performing smoke tests.

---

## Groups and Tasks

### 1. Clean Group

The `clean` group is responsible for removing temporary and unnecessary files
generated during development.

#### Tasks:

- `tmp`: Cleans up various build artifacts and temporary files
  - Removes directories:
    - `build/`
    - `dist/`
    - `.eggs/`
    - `.pytest_cache`
    - `.ruff_cache`
    - `.mypy_cache`
  - Deletes specific file types:
    - `*.egg`
    - `*.egg-info`
    - `*.pyc`
    - `*.pyo`
    - `__pycache__`
    - Temporary files (`*~`)

### 2. Documentation Group

The `docs` group manages documentation-related tasks.

#### Tasks:

- `build`: Generates documentation using MkDocs

  - Builds documentation with `mkdocs build`
  - Uses configuration from `mkdocs.yaml`

- `preview`: Locally serves documentation
  - Starts MkDocs development server
  - Watches `docs` directory for changes
  - Uses configuration from `mkdocs.yaml`

### 3. Release Group

The `release` group handles software release processes using semantic-release.

#### Variables:

- `app`: A complex NPX command that sets up semantic-release with multiple
  plugins
  - Includes plugins for:
    - Conventional commits
    - Commit analysis
    - Release notes generation
    - Changelog management
    - GitHub integration
    - Git operations

#### Tasks:

- `ci`: Runs semantic-release in continuous integration mode
- `dry`: Performs a dry run of the release process
  - Executes semantic-release without actual publishing
  - Builds the package using Poetry
  - Simulates package publication

### 4. Tests Group

The `tests` group manages various testing and validation tasks.

#### Tasks:

- `linter`: Runs pre-commit hooks to enforce coding standards
- `unittest`: Executes unit tests using pytest
- `smoke`: Runs a comprehensive suite of smoke tests
  - Includes multiple predefined smoke tests to validate different aspects of
    the system
- `ci`: Comprehensive CI/CD validation task
  - Runs linter
  - Executes unit tests
  - Runs smoke tests
  - Builds documentation

### 5. Smoke Tests Group

The `smoke-tests` group contains an extensive collection of tests to validate
Makim's functionality across various scenarios.

#### Tests Include:

1. Simple configuration tests
2. Complex configuration tests
3. Container integration tests
4. Shell application tests
5. Unit tests
6. Environment variable handling
7. Variable processing
8. Bash shell testing
9. Directory path handling (absolute, relative, no-path)
10. Interactive argument processing
11. Hook execution
12. Matrix strategy testing
13. Remote SSH execution
14. Scheduler functionality

### 6. Error Group

The `error` group is designed to test failure scenarios and error handling.

#### Tasks:

- `python-assert`: Demonstrates Python assertion failure
- `code-3`: Shows bash script exit with error code 3

### 7. Docker Group

The `docker` group manages Docker-related tasks for testing SSH connections.

#### Tasks:

- `build`: Builds a Docker image for SSH testing
  - Uses Dockerfile in the `containers` directory
- `start`: Launches a Docker container for SSH testing
  - Runs container with port mapping
  - Includes pre-run hook to build the image
- `stop`: Stops the SSH test container
- `test`: Verifies SSH connection to the Docker service
  - Removes previous SSH host key
  - Connects to localhost on port 2222

## Task Execution

To run a specific task, use the following command:

```bash
makim <group>.<task>
```

### Examples:

- Run unit tests: `makim tests.unittest`
- Build documentation: `makim docs.build`
- Clean temporary files: `makim clean.tmp`

## Additional Features

- Support for environment variables
- Pre-run and post-run hooks
- Interactive arguments
- Verbose mode options
- Matrix strategy testing

## Best Practices

1. Always use verbose mode (`--verbose`) for detailed output during testing
2. Utilize hooks for complex task dependencies
3. Leverage environment-specific configurations
4. Regularly clean up temporary files
5. Use matrix strategies for comprehensive testing

This document serves as a reference for understanding and maintaining the
`.makim.yaml` file.
