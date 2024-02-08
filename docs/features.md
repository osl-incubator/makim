## version: 1.0

# Groups

## Default

### makim env-file

A .env file is a configuration file that defines environment-specific variables. It is written in YAML (YAML Ain't Markup Language). 

You can use multiple .env files in your compose.yml with the env_file attribute. If the same variable is defined in multiple files, the last definition takes precedence:

The `env-file` attribute can be specified at three different
scopes: global, group, and target. It allows users to set the working
scope for a specific target, a group of targets, or globally.]

### Makim's env file is stored at       
tests/.makim-env.yaml

```
makim/tests/.makim-env.yaml
```

### Syntax and Scopes
The env-file attribute can be applied to three different scopes:

- #### **Global Scope**
    Setting the global env-file impacts all targets and groups in
    the Makim configuration. This env-file works universally in that program.

    ```yaml
    global-scope:
    targets:
      test-var-env-file:
        help: Test env variable defined in the global scope from env-file
        run: |
          import os
          assert str(os.getenv("ENV")) == "dev"
      test-var-env:
        help: Test env variable defined in the global scope in `env` section
        run: |
          import os
          assert str(os.getenv("GLOBAL_VAR_1")) == "1"
          assert str(os.getenv("GLOBAL_VAR_2")) == "2"
    ```

- #### Group Scope
    env-file can also have group scope.
    Setting the env-file at the group scope affects all targets within  that group.
    This file only works for the specified group.

    ```yaml

    group-scope:
    env-file: .env-group
    env:
      GROUP_VAR_1: 1
      GROUP_VAR_2: 2
    targets:
      test-var-env-file:
        help: Test env variable defined in the global scope from env-file
        run: |
          import os
          assert str(os.getenv("ENV")) == "prod"

      test-var-env:
        help: Test env variable defined in the global scope in `env` section
        run: |
          import os
          assert str(os.getenv("GROUP_VAR_1")) == "1"
          assert str(os.getenv("GROUP_VAR_2")) == "2"
    
    ```

- #### Target Scope

    Setting the env-file scope at the target allows for fine grained
    control over individual targets.
    


## Example

```yaml
version: 1.0
working-directory: /project-root

groups:
  target-scope:
    targets:
      test-var-env-file:
        help: Test env variable defined in the global scope from env-file
        env-file: .env-target
        run: |
          import os
          assert str(os.getenv("ENV")) == "test"

      test-var-env:
        help: Test env variable defined in the global scope in `env` section
        env-file: .env-target
        env:
          TARGET_VAR_1: 1
          TARGET_VAR_2: 2
          ENV: staging
        run: |
          import os
          assert str(os.getenv("TARGET_VAR_1")) == "1"
          assert str(os.getenv("TARGET_VAR_2")) == "2"
          assert str(os.getenv("ENV")) == "staging"


```

# targets:

## TARGET-NAME

### Attribute: help clean
 
 We can simply remove the unneccessary file using the target commands:
 - run the clean target: makim clean
- run the build target with the clean flag: makim build --clean

We can use the default selected target and use the clean command with our default target.
  - default.clean => Use this target to clean up temporary files.
     - ARGS:
          --all: (bool) Remove all files that are tracked by git.


### Arguments
Arguments can be defined in a `args` section for each target and they can have different types (-all, --clean etc)
The help menu for the .makim.yaml file contains the possible args 
you can use:

--all
This arg is used in `default.clean` target. It removes all  the temporary files that are not tracked by git.

--clean 
This bool  arg is used in `default.build` is used to clean the unnecessary file after build.

Both --args are bool type, which if not set will not be trigerred.

The help menu for the .makim.yaml file would looks like this:

```yaml
   $ makim --help
usage: MakIm [--help] [--version] [--config-file MAKIM_FILE] [target]

MakIm is a tool that helps you to organize and simplify your helper commands.

Options:
  -v, --version                   Show the version and exit
  --file TEXT                     Makim config file  [default: .makim.yaml]
  --dry-run                       Execute the command in dry mode
  --verbose                       Execute the command in verbose mode
  --install-completion [bash|zsh|fish|powershell|pwsh]
                                  Install completion for the specified shell.
  --show-completion [bash|zsh|fish|powershell|pwsh]
                                  Show completion for the specified shell, to
                                  copy it or customize the installation.
  --help                          Show this message and exit.

Commands:
  clean.tmp                       Clean unnecessary...
  docs.build                      Build documentation
  docs.preview                    Preview documentation page...
  release.ci                      Run semantic release on CI
  release.dry                     Run semantic release in...
  smoke-tests.bash                Test makim shell attribute...
  smoke-tests.complex             Test makim using a complex...
  smoke-tests.containers          Test makim with...
  smoke-tests.shell-app           Test makim with...
  smoke-tests.simple              Test makim using a simple...
  smoke-tests.unittest            Test makim using a...
  smoke-tests.vars-env            Test makim using env...
  smoke-tests.working-directory-absolute-path
                                  Test makim with...
  smoke-tests.working-directory-no-path
                                  Test makim with...
  smoke-tests.working-directory-relative-path
                                  Test makim with...
  tests.ci                        Run all targets used on CI
  tests.linter                    Run linter tools
  tests.smoke                     Run smoke tests
  tests.unittest                  Run tests

  If you have any problem, open an issue at: https://github.com/osl-
  incubator/makim
```

As you can see, the help menu automatically adds information defined by all the help key, inside the .makim.yaml file.

.### Attribute: Run
MakIm or just makim is based on make and focus on improve the way to define targets and dependencies. Instead of using the Makefile format, it uses yaml format.

The run atrributes in MakIm is used to run the build.


### How to Run it
First you need to place the config file .makim.yaml in the root of your project. This is an example of a configuration file:

   ```yaml
    version: 1.0.0
groups:
  default:
    env-file: .env
    targets:
      clean:
        help: Use this target to clean up temporary files
        args:
          all:
            type: bool
            action: store_true
            help: Remove all files that are tracked by git
        run: |
          echo "remove file X"
      build:
        help: Build the program
        args:
          clean:
            type: bool
            action: store_true
            help: if not set, the clean dependency will not be triggered.
        dependencies:
          - target: clean
            if: {{ args.clean == true }}
        run: |
          echo "build file x"
          echo "build file y"
          echo "build file z"
```
Some examples of how to use it:

- run the build target: makim build

- run the clean target: makim clean

- run the build target with the clean flag: makim build --clean

## Attribute: dependencies
 
 Makim needs the following directories to install and  run smoothly.

- xonsh 
- typing-extensions
- sh
- pyyaml 
- python-dotenv
- MarkupSafe 
- colorama 
- jinja2 
- click 
- typer.

Genrally this is automatically handled when installing the makim. If there is is an existing  problem with your system 
in any of this packages, makim may show errors. So make sure to resolve and install them.