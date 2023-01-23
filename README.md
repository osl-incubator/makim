# MakIm

`MakIn` or just `makin` is based on `make` and focus on improve
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
            if: ${{ args.clean == true }}
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
