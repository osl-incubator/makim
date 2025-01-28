# Features

## Overview

Makim is a task management tool inspired by `make`, designed to simplify
defining and executing tasks with dependencies. It replaces traditional
`Makefile` formats with a user-friendly `YAML` configuration system, offering
flexibility, modularity, and better readability. Here are Makim's key features:

## Key Features

### 1. Attribute: dir

The `dir` feature allows users to define the working directory for tasks,
groups, or the entire configuration. This ensures commands run in the intended
environment, providing control over execution contexts.

**Syntax and Scopes**

- **Global Scope**: Applies to all tasks and groups.

- **Group Scope**: Overrides the global directory for specific groups.

- **Task Scope**: Offers fine-grained control for individual tasks.

**Example**

```yaml
version: 1.0
dir: /project-root

groups:
  backend:
    dir: backend
    tasks:
      build:
        dir: services
        run: |
          echo "Building backend services..."

      test:
        dir: tests
        run: |
          echo "Running backend tests..."
```

### 2. Scoped Environment Variables

Environment variables can be defined at global, group, or task levels, ensuring
modular configurations.

**Example**

```yaml
groups:
  my-group:
    env:
      NODE_ENV: production
    tasks:
      start:
        env:
          DEBUG: true
        run: |
          echo $NODE_ENV
          echo $DEBUG
```

### 3. Matrix Configuration

Define and run tasks with multiple parameter combinations. Perfect for CI/CD
pipelines or testing scenarios.

**Example**

```yaml
groups:
  test-group:
    tasks:
      test-matrix:
        matrix:
          env:
            - dev
            - staging
            - prod
        run: |
          echo "Testing in $env"
```

### 4. Hooks (pre-run and post-run)

Run additional tasks before or after a primary task to set up or clean up
resources.

**Example**

```yaml
groups:
  build-group:
    tasks:
      build:
        hooks:
          pre-run:
            - task: setup-environment
          post-run:
            - task: cleanup
        run: |
          echo "Building project..."
```

### 5. Scheduler

Makim integrates with APScheduler for cron-like task scheduling. Define tasks to
run at specified intervals using cron expressions.

**Example**

```yaml
scheduler:
  daily-backup:
    task: backup
    schedule: "0 3 * * *" # Runs daily at 3 AM
    args:
      path: /backup
```

### 6. Dynamic Command Generation

Makim dynamically generates CLI commands from the `.makim.yaml` configuration,
enabling streamlined task execution.

**Example**

```yaml
makim build # Executes the build task as defined in .makim.yaml
```

### 7. Remote Command Execution

Makim supports executing tasks on remote servers via SSH with customizable
configurations.

**Example**

```yaml
groups:
  remote-group:
    tasks:
      deploy:
        remote: my-server
        run: |
          echo "Deploying application..."

hosts:
  my-server:
    username: user
    host: example.com
    port: 22
    password: pass
```

### 8. Configuration Validation

Makim validates `.makim.yaml` against a predefined JSON schema to catch errors
early and ensure correctness.
