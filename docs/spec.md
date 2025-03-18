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
{% raw %}
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
{% endraw %}
```

---

## 3. Tasks

### Description

Tasks define executable commands with optional arguments, dependencies, and
hooks.

### Structure

```yaml
{% raw %}
tasks:
  <task_name>:
    help: <description>
    args: <arguments>
    env: <environment_variables>
    hooks: <pre/post-run_hooks>
    matrix: <parameter_combinations>
    log: <file_logging_configuration>
    run: <command>
{% endraw %}
```

### Example

```yaml
{% raw %}
tasks:
  test:
    help: Run tests
    args:
      verbose:
        type: bool
        action: store_true
    run: pytest --verbose=${{ args.verbose }}
{% endraw %}
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
executes. They can also include an `if` condition to control when the hook
should be triggered.

### Structure

```yaml
hooks:
  pre-run:
    - task: <task_name>
      if: <condition>
  post-run:
    - task: <task_name>
      if: <condition>
```

### Example

```yaml
{% raw %}
tasks:
  build:
    hooks:
      pre-run:
        - task: clean
          if: ${{ vars.REBUILD == "true" }}
      post-run:
        - task: notify
    run: echo "Building project..."
{% endraw %}
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
  API_KEY: abc
  RETRY_COUNT: "3"
```

### Note:

⚠️ The value of an environment variable should always be a string. If you need
to pass an integer, wrap it in quotes (`""`) to avoid type issues.

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
    - macos
```

---

## 8. Scheduler

### Description

Defines scheduled tasks using **cron syntax**, allowing periodic execution of
tasks.

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

### Understanding Cron Syntax

A cron expression consists of **five fields**, each representing a time unit:

| Field            | Value Range        | Example | Meaning                           |
| ---------------- | ------------------ | ------- | --------------------------------- |
| **Minute**       | `0-59`             | `30`    | Runs at 30th minute               |
| **Hour**         | `0-23`             | `2`     | Runs at 2 AM                      |
| **Day of Month** | `1-31`             | `15`    | Runs on the 15th day of the month |
| **Month**        | `1-12`             | `6`     | Runs in June                      |
| **Day of Week**  | `0-6` (Sunday = 0) | `1`     | Runs on Monday                    |

### Common Cron Examples

- `0 0 * * *` → Runs **daily at midnight**
- `30 14 * * 5` → Runs **every Friday at 2:30 PM**

For a detailed guide on cron syntax, visit:

📌 [Cron Syntax Guide](https://crontab.guru/)

## 9. Remote Hosts

### Description

Defines SSH configurations for executing tasks on remote servers. Additionally,
tasks can specify a `remote` entry to execute commands on a defined host.

### Structure

```yaml
hosts:
  <host_name>:
    username: <user>
    host: <hostname>
    port: <port>
    password: <password>
```

Using Remote Execution Inside a Task

```
tasks:
  <task_name>:
    remote: <host_name>
    run: <command>
```

### Example

#### 1. Define Remote Host

```yaml
hosts:
  production:
    username: user
    host: example.com
    port: 22
```

#### 2. Execute Task on Remote Server

```yaml
tasks:
  deploy:
    remote: production
    run: echo "Deploying application..."
```

**Explanation:**

- The `hosts` section defines the `production` remote server.
- The `deploy` task specifies `remote: production`, ensuring it runs on
  `example.com` via SSH.

---

## 10. File Logging

### Description

Defines the configuration for tasks to write their output to a file with
optional custom formatting and control over which output types are logged.

### Structure

```yaml
log:
  path: <log_file_path>
  level: <output_type>
  format: <log_format_string>
```

#### Example

```yaml
tasks:
  build:
    help: Build the application
    log:
      path: ./logs/build.txt
      level: both
      format: "%(asctime)s - %(levelname)s - %(message)s"
    run: |
      echo "Building..."
```

### Supported Format Placeholders

- `%(asctime)s` — Timestamp of the log entry.
- `%(task)s` — Name of the task being executed.
- `%(file)s` — File name where the task is defined.
- `%(levelname)s` — Output type label (`OUT` or `ERR`).
- `%(message)s` — Actual log output.

---

## 11. Variables

### Description

Defines reusable variables that can be referenced throughout the configuration.

### Supported Scopes:

- **Global** – Available everywhere.
- **Group** – Available within a specific group.
- **Task** – Available only within a task.

### Structure

```yaml
vars:
  <var_name>: <value>
```

### Example

```yaml
vars:
  PROJECT_NAME: MyApp
  TIMEOUT: 30
```

This can be used in tasks as:

```yaml
{% raw %}
tasks:
  deploy:
    run: echo "Deploying ${{ vars.PROJECT_NAME }} with timeout ${{ vars.TIMEOUT }}s"
{% endraw %}
```

## 12. Environment Variables

### Description

Loads environment variables from an external `.env` file. This is useful for
managing secrets and configurations separately.

### Supported Scopes:

- **Global** – Available everywhere.
- **Group** – Available within a specific group.
- **Task** – Available only within a task.

### Structure

```
env-file: <path_to_env_file>
```

### Example

```
env-file: .env
```

This will automatically load the environment variables defined in `.env`.
