# Overview

Makim is a task automation tool that enhances the way tasks and dependencies are
defined using YAML instead of Makefile syntax. This document explains Makim's
features in detail, providing use cases and benefits for developers and teams
looking to simplify and automate workflows efficiently.

---

# Features

## 1. Help Text

### What It Does

Makim allows you to add detailed `help` text to tasks and their arguments. This
improves documentation and makes it easier for users to understand how to use
each task.

### Use Case

Developers often forget how a certain script works. With Makim, they can simply
run:

```sh
makim --help
```

And get an automatically generated help menu with clear descriptions for tasks
and arguments.

---

## 2. Task Arguments

### What It Does

Makim allows tasks to accept arguments with predefined types, default values,
and descriptions.

### Use Case

Suppose you have a task that clears the cache but also wants an option to remove
all build artifacts:

```yaml
tasks:
  clean:
    help: Clean build artifacts
    args:
      cache:
        type: bool
        action: store_true
        help: Remove all cache files
    run: rm -rf build/
```

You can run:

```sh
makim clean --cache
```

### Benefit

- Prevents hardcoded parameters in scripts.
- Offers a flexible way to pass arguments dynamically.

---

## 3. Environment Variables

### What It Does

Makim allows scoping environment variables globally, at the group level, or at
the task level.

### Use Case

If different tasks need different environment variables, you can define:

```yaml
groups:
  build:
    env:
      GROUP_ENV: group_value
```

### Benefit

- Avoids redundant variable definitions.
- Increases modularity in task execution.

---

## 4. Jinja2 Templating

### What It Does

Makim integrates with Jinja2 templating, allowing dynamic access to arguments
and environment variables.

### Use Case

You can use Jinja2 to dynamically insert values:

```yaml
{% raw %}
tasks:
  greet:
    help: Print a greeting
    args:
      name:
        type: str
        help: Name of the person to greet
    run: echo "Hello, ${{ args.name }}!"
{% endraw %}
```

Running:

```sh
makim greet --name John
```

Outputs:

```
Hello, John!
```

### Benefit

- Adds flexibility in command execution.
- Reduces the need for complex shell scripting.

---

## 5. Matrix Configuration

### What It Does

Makim allows running tasks across multiple parameter combinations, making it
useful for CI/CD workflows.

### Use Case

If you need to test across multiple environments:

```yaml
{% raw %}
tasks:
  test:
    matrix:
      python_version:
        - 3.8
        - 3.9
        - 3.10
      os:
        - ubuntu
        - macos
    run:
      echo "Running test on Python ${{ matrix.python_version }} and OS ${{
      matrix.os }}"
{% endraw %}
```

Makim automatically expands this into multiple runs for each combination.

### Benefit

- Automates testing across configurations.
- Reduces manual setup in CI/CD pipelines.

---

## 6. Hooks

### What It Does

Makim provides `pre-run` and `post-run` hooks to execute tasks before or after
another task runs.

### Use Case

If you need to clean before compiling:

```yaml
groups:
  build:
    tasks:
      compile:
        hooks:
          pre-run:
            - task: build.clean
          post-run:
            - task: build.notify
        run: echo "Compiling source code..."

      clean:
        help: Clean build artifacts
        run: rm -rf build/

      notify:
        help: Notify team about successful compilation
        run: echo "Build completed successfully!"
```

### Skipping Hooks

Makim allows you to skip hooks during execution using the `--skip-hooks` flag.
This is useful when you want to run a task without executing its associated
hooks.

For example, to run the `compile` task while skipping all hooks:

```sh
makim --skip-hooks build.compile
```

### Benefit

- Automates task chaining.
- Reduces duplication of logic.

---

## 7. Scheduler (Cron-like Automation)

### What It Does

Makim integrates with APScheduler to allow periodic execution of tasks using
cron syntax.

### Use Case

If you need to run a cleanup task daily at midnight:

```yaml
scheduler:
  daily-clean:
    task: build.clean
    schedule: "0 0 * * *"
```

### How to run?

To start the scheduler, run:

```
makim cron start daily-clean
```

To stop the scheduler, run:

```
makim cron stop daily-clean
```

### Benefit

- Automates repetitive tasks.
- Reduces manual intervention.

---

## 8. Remote Execution

### What It Does

Makim allows running tasks on remote servers via SSH with flexible
configurations.

### More Details

For detailed specifications on Remote Execution, please refer to the
[**Makim spec documentation**](./spec.md).

Makim’s remote execution capabilities are similar to tools like:

- [Ansible](https://docs.ansible.com) – Automates IT infrastructure and
  application deployment.
- [Fabric](https://www.fabfile.org/) – A Python library for executing remote
  shell commands over SSH.

### Benefit

- Automates remote deployments.
- Eliminates the need for manual SSH logins.

---

## 9. File Logging

### What It Does

Makim allows tasks to log their outputs to a file with custom formatting. You
can choose to log standard output, standard error, or both using `level`
property

### Use Case

If you want to analyze build outputs

```yaml
tasks:
  build:
    help: Build source code
    log:
      path: ./logs/build.txt
      level: both
      format: "%(asctime)s - %(levelname)s - %(message)s"
    run: |
      echo "Compiling source code..."
```

### Benefit

- Review logs for monitoring.
- Capture errors for diagnosing issues.

---

## 10. Validation

### What It Does

Makim ensures that `.makim.yaml` configurations are correctly formatted using
schema validation.

### Use Case

Before running any tasks, Makim checks for syntax errors and missing fields,
preventing misconfigurations.

### Benefit

- Reduces runtime errors.
- Improves reliability of task execution.

---
