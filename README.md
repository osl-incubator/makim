# MakIm

`MakIm` or just `makim` is based on `make` and focus on improve
the way to define targets and dependencies. Instead of using the
`Makefile` format, it uses `yaml` format.

The idea of this project is to offer a way to define targets and
dependencies with some control options, like conditionals `if`.

It allows a very easy way to define texts for documentation and
extra parameters for each target.


* Free software: BSD 3 Clause
* Documentation: https://osl-incubator.github.io/makim

## Features

* Help text as first-class in the `.makim.yaml` specification. It can be used by targets and arguments.
* Targets have an option for arguments.
* Targets have an option for dependencies.
* Dependencies can call a target with specific arguments.
* Dependencies can have a conditional control flow (`if`).
* Allow the creation of groups, so the targets can be organized by topics.
* Targets and groups have an option for user defined variables and/or environment variables.
* Access arguments, variables or environment variables via template (using Jinja2).
* Option for using dot environment files using `env-file` key.

## How to use it

First you need to place the config file `.makim.yaml` in the root of your project.
This is an example of a configuration file:

```yaml
version: 1.0.0
groups:
  default:…nary

## Pull Request description
<!-- Describe the purpose of your PR and the changes you have made. -->

<!-- Which issue this PR aims to resolve or fix? E.g.:
Solving issue #004
-->

## How to test these changes

<!-- Example:

* run `$ abc -p 1234`
* open the web browser with url localhost:1234
* ...
-->

* ```...```

<!-- Modify the options to suit your project. -->
## Pull Request checklists

This PR is a:
- [ ] bug-fix
- [ ] new feature
- [ ] maintenance

About this PR:
- [ ] it includes tests.
- [ ] the tests are executed on CI.
- [ ] the tests generate log file(s) (path).
- [ ] pre-commit hooks were executed locally.
- [ ] this PR requires a project documentation update.

Author's checklist:
- [ ] I have reviewed the changes and it contains no misspelling.
- [ ] The code is well commented, especially in the parts that contain more complexity.
- [ ] New and old tests passed locally.

## Additional information

<!-- Add any screenshot that helps to show the changes proposed -->

<!-- Add any other extra information that would help to understand the changes proposed by this PR -->

## Reviewer's checklist

Copy and paste this template for your review's note:

```
## Reviewer's Checklist

- [ ] I managed to reproduce the problem locally from the `main` branch
- [ ] I managed to test the new changes locally
- [ ] I confirm that the issues mentioned were fixed/resolved .
```

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
            if: {% raw %}{{ args.clean == true }}{% endraw %}
        run: |
          echo "build file x"
          echo "build file y"
          echo "build file z"
```

Some examples of how to use it:

* run the `build` target:
  `makim build`

* run the `clean` target:
  `makim clean`

* run the `build` target with the `clean` flag:
  `makim build --clean`


The help menu for the `.makim.yaml` file would looks like this:

```
$ makim --help
usage: MakIm [--help] [--version] [--config-file MAKIM_FILE] [target]

MakIm is a tool that helps you to organize and simplify your helper commands.

positional arguments:
  target
    Specify the target command to be performed.
    Options are:
      default.clean => Use this target to clean up temporary files
        ARGS:
          --all: (bool) Remove all files that are tracked by git
      default.build => Build the program
        ARGS:
          --clean: (bool) if not set, the clean dependency will not be triggered.
    NOTE: 'default.' prefix is optional.

options:
  --help, -h
    Show the help menu
  --version
    Show the version of the installed MakIm tool.
  --config-file MAKIM_FILE
    Specify a custom location for the config file.

If you have any problem, open an issue at: https://github.com/osl-incubator/makim
```

As you can see, the help menu automatically adds information defined by all
the `help` key, inside the `.makim.yaml` file.

## Xonsh Shell Integration

### What is Xonsh?
[Xonsh](https://xon.sh/) is a powerful shell language and command prompt designed to seamlessly blend traditional shell capabilities with the expressive syntax of Python. It offers an interactive and extensible environment that enables users to transition effortlessly between standard shell commands and Python scripting.

### How Xonsh enhances this Project?
In the context of this project, Xonsh serves as the default shell for executing commands defined in the Makim configuration. By leveraging Xonsh, the Makim tool gains the flexibility and richness of the Python programming language within a command-line interface. This integration allows users to create sophisticated tasks and harness the full power of Python directly in the terminal.

### Key Features and Commands in Xonsh
1. **Unified Syntax :** Xonsh seamlessly integrates traditional shell syntax with Python's clean and expressive syntax, creating a unified and consistent scripting experience.
```
# Shell-style command
ls -l

# Python-style variable assignment
$filename = "example.txt"

# Combining both in a single command
echo "The contents of $filename are: $(cat $filename)"
```

2. **Python Variables and Expressions :** Python variables can be easily incorporated into commands, enhancing the readability and flexibility of your scripts.
```
$filename = "example.txt"
echo "The filename is $filename"
```

3. **Looping and Conditional Statements :** Use Python-style loops and conditionals to create dynamic and complex command sequences.
```
for $i in range(3):
    echo "Iteration $i"
```

4. **Extensible Tab Completion :** Xonsh offers extensible and intelligent tab completion, making it easier to discover and complete commands and variables.
```
$long_variable_name = "some_value"
echo $long_<TAB>
# Xonsh will intelligently complete the variable name
```


### Getting Started with Xonsh
To integrate Xonsh into your project, install it using:
```
pip install xonsh
```

Launch the Xonsh shell by running:
```
xonsh
```

For more comprehensive information and documentation, explore the [Xonsh GitHub repository](https://github.com/xonsh/xonsh) and the official [Xonsh website](https://xon.sh/).