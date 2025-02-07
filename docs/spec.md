# Makim Specification

## Overview

Makim uses a YAML-based configuration file (`.makim.yaml`) to define tasks,
dependencies, and execution environments. This document provides a detailed
specification of all components available in a Makim configuration file.

## 1. File Structure

A `.makim.yaml` file consists of the following top-level sections:

- `groups`
- `scheduler`
- `hosts`
- `vars`
- `env`
- `env-file`

Each section is explained below in detail.

---

## 2. Groups

### Description

Defines collections of related tasks. Each group contains tasks and environment
variables specific to that group.

### Structure

```yaml
groups:
  <group_name>:
    env:
      <key>: <value>
    tasks:
      <task_name>: <task_definition>
```

### Example

```yaml
groups:
  build:
    env:
      BUILD_DIR: dist
    tasks:
      clean:
        help: Clean build artifacts
        run: rm -rf ${{ env.BUILD_DIR }}
      compile:
        help: Compile the project
        run: echo "Compiling..."
```

---

## 3. Tasks

### Description

Tasks define executable commands with optional arguments, dependencies, and
hooks.

### Structure

```yaml
tasks:
  <task_name>:
    help: <description>
    args: <arguments>
    env: <environment_variables>
    hooks: <pre/post-run_hooks>
    matrix: <parameter_combinations>
    run: <command>
```

### Example

```yaml
tasks:
  test:
    help: Run tests
    args:
      verbose:
        type: bool
        action: store_true
    run: pytest --verbose=${{ args.verbose }}
```

---

## 4. Arguments

### Description

Defines arguments that tasks can accept with types, defaults, and help
descriptions.

### Structure

```yaml
args:
  <arg_name>:
    type: <type>
    default: <default_value>
    interactive: <true/false>
    help: <description>
```

### Example

```yaml
args:
  env:
    type: str
    default: "dev"
    help: Environment setting
```

---

## 5. Hooks

### Description

Hooks define tasks that run before (`pre-run`) or after (`post-run`) a task
executes.

### Structure

```yaml
hooks:
  pre-run:
    - task: <task_name>
  post-run:
    - task: <task_name>
```

### Example

```yaml
hooks:
  pre-run:
    - task: clean
```

---

## 6. Environment Variables

### Description

Defines global, group, or task-specific environment variables.

### Structure

```yaml
env:
  <key>: <value>
```

### Example

```yaml
env:
  API_KEY: abc123
```

---

## 7. Matrix Configuration

### Description

Defines multiple combinations of parameters for running a task.

### Structure

```yaml
matrix:
  <param_name>:
    - <value1>
    - <value2>
```

### Example

```yaml
matrix:
  python_version:
    - 3.8
    - 3.9
    - 3.10
  os:
    - ubuntu
    - macos]
```

---

## 8. Scheduler

### Description

Defines scheduled tasks using cron syntax.

### Structure

```yaml
scheduler:
  <schedule_name>:
    task: <task_name>
    schedule: <cron_expression>
```

### Example

```yaml
scheduler:
  daily-clean:
    task: build.clean
    schedule: "0 0 * * *"
```

---

## 9. Remote Hosts

### Description

Defines SSH configuration for executing tasks on remote servers.

### Structure

```yaml
hosts:
  <host_name>:
    username: <user>
    host: <hostname>
    port: <port>
    password: <password>
```

### Example

```yaml
hosts:
  my_server:
    username: user
    host: example.com
    port: 22
```

---

## Conclusion

This document outlines the complete specification for `.makim.yaml`, covering
all components, their syntax, and usage examples. Understanding these elements
enables users to define efficient and scalable task automation workflows using
Makim.
