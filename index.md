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


## How to use it

First you need to place the config file `.makim.yaml` in the root of your project.
This is an example of a configuration file:

```yaml
version: 1.0.0
shell: bash
groups:
  - name: default
    env-file: .env
    targets:
      clean:
        help: Use this target to clean up temporary files
        args:
          all:
            type: bool
            action: store-true
            help: Remove all files that are tracked by git
        run: |
          echo "remove file X"
      build:
        help: Build the program
        args:
          clean:
            type: bool
            action: store-true
            help: if not set, the clean dependency will not be triggered.
        dependencies:
          - target: clean
            if: \${\{ args.clean == true \}\}
        run: |
          echo "build file x"
          echo "build file y"
          echo "build file z"

```

PS: in `\${\{ args.clean == true \}\}`, this `\` is just for escaping it for
the documentation here, you should use it with no escape `\`.

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
