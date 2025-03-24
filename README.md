# Makim

![CI](https://img.shields.io/github/actions/workflow/status/osl-incubator/makim/main.yaml?logo=github&label=CI)
[![Python Versions](https://img.shields.io/pypi/pyversions/makim)](https://pypi.org/project/makim/)
[![Package Version](https://img.shields.io/pypi/v/makim?color=blue)](https://pypi.org/project/makim/)
![License](https://img.shields.io/pypi/l/makim?color=blue)
![Discord](https://img.shields.io/discord/796786891798085652?logo=discord&color=blue)

**Makim** is inspired by tools like **Make** and **Ansible**, focusing on
improving task definition and dependency management. Instead of using the
**Makefile** format, it utilizes **YAML** for defining tasks.

- License: BSD 3 Clause
- Documentation: [Makim Docs](https://osl-incubator.github.io/makim)

---

## Features

- **Help Text as First-Class:** Add detailed `help` text to tasks and arguments
  for clear documentation.
- **Task Arguments:** Define and manage arguments with types, defaults, and
  descriptions.
- **Dependencies with Conditional Control:** Set task dependencies with `if`
  conditionals to manage execution dynamically.
- **Environment Variables:** Scope variables globally, by group, or by task to
  reduce redundancy and maintain modularity.
- **Jinja2 Templating:** Access arguments, variables, or environment variables
  via Jinja2 templates.
- **Matrix Configuration:** Automate tasks across multiple parameter
  combinations (ideal for CI/CD workflows).
- **Hooks:** Use `pre-run` and `post-run` hooks to customize task lifecycles.
- **Scheduler:** Cron-like scheduling with APScheduler integration for periodic
  tasks.
- **Remote Execution:** Execute tasks on remote servers via SSH with flexible
  configurations.
- **File Logging:** Log outputs to files with custom formatting and stream
  control.
- **Retry Mechanism:** Adds resilience by retrying tasks that encounter errors.
- **Validation:** Ensures `.makim.yaml` configurations are correct with schema
  validation.

---

## How to use it

First you need to place the config file `.makim.yaml` in the root of your
project. This is an example of a configuration file:

```yaml
groups:
  build:
    env:
      GROUP_ENV: group_value
    tasks:
      clean:
        help: Clean build artifacts
        args:
          cache:
            type: bool
            action: store_true
            help: Remove all cache files
        log:
          path: ./logs/clean.txt
          level: err
          format: "%(asctime)s - %(file)s - %(levelname)s - %(message)s"
        run: |
          echo "Cleaning build directory..."
          rm -rf build/
      compile:
        help: Compile the project
        hooks:
          pre-run:
            - task: build.clean # Run 'clean' before 'compile'
        run: |
          echo "Compiling the project..."

# Scheduler for automated tasks
scheduler:
  daily-clean:
    task: build.clean
    schedule: "0 0 * * *" # Every day at midnight
```

Some examples of how to use it:

- run the `compile` task: `makim build.compile`

- run the `clean` task with argument: `makim build.clean --cache`

The help menu for the `.makim.yaml` file would looks like this:

```
$ makim --help

 Usage: makim [OPTIONS] COMMAND [ARGS]...

 Makim is a tool that helps you to organize and simplify your helper commands.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --version             -v            Show the version and exit                │
│ --file                        TEXT  Makim config file [default: .makim.yaml] │
│ --dry-run                           Execute the command in dry mode          │
│ --verbose                           Execute the command in verbose mode      │
│ --skip-hooks                        Skip hooks while executing the command   │
│ --install-completion                Install completion for the current       │
│                                     shell.                                   │
│ --show-completion                   Show completion for the current shell,   │
│                                     to copy it or customize the              │
│                                     installation.                            │
│ --help                              Show this message and exit.              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ build ──────────────────────────────────────────────────────────────────────╮
│ build.clean                         Clean build artifacts                    │
│ build.compile                       Compile the project                      │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Extensions ─────────────────────────────────────────────────────────────────╮
│ cron                                Tasks Scheduler                          │
╰──────────────────────────────────────────────────────────────────────────────╯

 If you have any problem, open an issue at: https://github.com/osl-incubator/makim
```

As you can see, the help menu automatically adds information defined by all the
`help` key, inside the `.makim.yaml` file.

## Playground

Experience **makim** directly in your browser using Google Colab! Google Colab
is an online platform that allows you to write, run, and share Python code
through your browser. It is especially useful for machine learning, data
analysis, and education.

To try makim, simply click the following link, make a copy of the notebook to
your drive, and then you can modify and execute the code as needed:

[Experiment with makim on Google Colab](https://colab.research.google.com/drive/1m131pqi6Bjq8Hp8YN_Cbuyezn61f19lB?usp=sharing)
