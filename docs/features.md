# Makim Features

## Working Directory Feature

The working-directory feature in Makim allows users to define the directory
from which commands associated with specific targets or groups are executed.
This provides greater flexibility and control over the execution environment.

### Attribute: working-directory

The `working-directory` attribute can be specified at three different
scopes: global, group, and target. It allows users to set the working
directory for a specific target, a group of targets, or globally.

### Benefits:

- **Isolation of Commands:**
  Users can isolate commands within specific directories, preventing
  potential conflicts and ensuring that commands run in the expected
  environment.

- **Flexibility in Configuration:**
  Different targets or groups may require different execution environments.
  The `working-directory` attribute offers the flexibility to customize
  these environments based on specific project needs.

- **Ease of Use:**
  The Makim configuration becomes more readable and maintainable as users
  can easily understand and manage the execution context of commands.

- **Support for Absolute and Relative Paths:**
  The feature supports both absolute and relative paths, allowing users to
  specify directories based on their project requirements.


### Syntax and Scopes
The working-directory attribute can be applied to three different scopes:

- #### **Global Scope**
    Setting the global working directory impacts all targets and groups in
    the Makim configuration.

    ```yaml
    version: 1.0
    working-directory: /path/to/global/directory

    # ... other configuration ...
    ```

- #### Group Scope

    Setting the working directory at the group scope affects all targets within
    that group.

    ```yaml

    version: 1.0

    groups:
        my-group:
            working-directory: /path/to/group/directory
            targets:
                target-1:
                    run: |
                    # This target will run with the working directory set to
                    # /path/to/group/directory
    ```

- #### Target Scope

    Setting the working directory at the target scope allows for fine grained
    control over individual targets.

    ```yaml
    version: 1.0
    groups:
        my-group:
            targets:
                my-target:
                    working-directory: /path/to/target/directory
                    run: | 
                    # This target will run with the working directory set to
                    # /path/to/target/directory
    ```

## Example

```yaml
version: 1.0
working-directory: /project-root

groups:
  backend:
    working-directory: backend
    targets:
      build:
        help: Build the backend services
        working-directory: services
        run: |
          echo "Building backend services..."
          # Additional build commands specific to the backend

      test:
        help: Run backend tests
        working-directory: tests
        run: |
          echo "Running backend tests..."
          # Additional test commands specific to the backend

  frontend:
    working-directory: frontend
    targets:
      build:
        help: Build the frontend application
        run: |
          echo "Building frontend application..."
          # Additional build commands specific to the frontend

      test:
        help: Run frontend tests
        run: |
          echo "Running frontend tests..."
          # Additional test commands specific to the frontend
```
