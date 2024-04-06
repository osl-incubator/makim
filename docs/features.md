# Features

## Attribute: dir

The dir feature in Makim allows users to define the directory from which
commands associated with specific tasks or groups are executed. This provides
greater flexibility and control over the execution environment.

The `dir` attribute can be specified at three different scopes: global, group,
and task. It allows users to set the working directory for a specific task, a
group of tasks, or globally.

### Syntax and Scopes

The dir attribute can be applied to three different scopes:

- #### **Global Scope**

  Setting the global working directory impacts all tasks and groups in the Makim
  configuration.

  ```yaml
  version: 1.0
  dir: /path/to/global/directory
  # ... other configuration ...
  ```

- #### Group Scope

  Setting the working directory at the group scope affects all tasks within that
  group.

  ```yaml
  version: 1.0

  groups:
    my-group:
      dir: /path/to/group/directory
      tasks:
        task-1:
          run: |
          # This task will run with the working directory set to
          # /path/to/group/directory
  ```

- #### Task Scope

  Setting the working directory at the task scope allows for fine grained
  control over individual tasks.

  ```yaml
  version: 1.0
  groups:
    my-group:
      tasks:
        my-task:
          dir: /path/to/task/directory
          run: |
          # This task will run with the working directory set to
          # /path/to/task/directory
  ```

## Example

```yaml
version: 1.0
dir: /project-root

groups:
  backend:
    dir: backend
    tasks:
      build:
        help: Build the backend services
        dir: services
        run: |
          echo "Building backend services..."
          # Additional build commands specific to the backend

      test:
        help: Run backend tests
        dir: tests
        run: |
          echo "Running backend tests..."
          # Additional test commands specific to the backend
```
