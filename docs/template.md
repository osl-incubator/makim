# Makim Template

**Makim** config files are powered by the Jinja2 template engine, allowing
you to use Jinja2 tags for added flexibility in your Makim config files.

This page focuses on explaining the options offered directly by **Makim**,
rather than covering all the possibilities with Jinja2.

**Makim** provides three different variable options that can be combined:
`vars`, `env`, and `args`.

Additionally, the `env` and `vars` option has three different scopes:
**global**, **group**, and **target**.
We will discuss each of them in the following sections.

## Variables Scopes

Before delving into the different variable options, let's discuss `env`
and `vars` scope, as it is essential for the subsequent sections.
The `args` attribute just works in the *target* scope.

As mentioned earlier, **Makim** `env` and `vars` has three scopes:
**global**, **group**, and **target**.

The order of their rendering is crucial. First, the *global* scope is processed.
In the *group* scope, any variable defined globally is accessible via the `env`
variable (e.g., `{% raw %}{{ env.my_global_env }}{% endraw %}`).
However, any variable defined in the *global* scope will be overridden by a
variable with the same name in the *group* scope. The same applies to the
*target* scope, where any variable defined in the *global* or *group* scope
will be overridden by a variable defined in the *target* scope.

Moreover, `env` is a bit more complex, as its value can be defined in two
different ways: either through the `env` attribute in the `.makim.yaml`
file or from an environment file specified in the `env-file` attribute.
First, the `env-file` is loaded into memory, and then the variables
defined in the `env` attribute are loaded. In other words, any variable
defined in the file for the given `env-file` will be overridden by a
variable of the same name defined in the `env` attribute. This process
also respects the order of scopes.

PS: **Makim** utilizes system environment variables as the initial scope for
the variables.

## Different Variable Options

**Makim** offers three variable options within the `makim` config file:
`env`, `vars`, and `args`.

* `args` allows users to pass parameters via the CLI (command line interface).
It can also be used for target dependencies when parameters need to be passed
to the dependency. However, this option is not available in the system context
(the commands executed defined by `run` attribute), it is only accessible
within the Makim config file.
* `vars` is a convenient way to define reusable variables in the code. For
example, if you frequently use a command in the `run` section, you can define
a variable inside `vars` to make the Makim file more readable. Like `args`,
this option is not available in the system context; it is only accessible
within the Makim config file.
* `env` is used to define environment variables. Any environment variable can
be accessed via the `env` variable in the template (e.g.,
`{% raw %}{{ env.myenvvar }}{% endraw %}`) or directly as an environment
variable within the `run` section, as shown in the example below:

```yaml
...
groups:
  group1:
    targets:
      target1:
        ...
        env:
          MYVAR: 1
        run: |
          echo $MYENV
```

## Order of Variable Rendering

One crucial point to keep in mind is the order of variable rendering
within the Makim config file.

`vars` is primarily used for `run` section,  so they have the lowest
precedence. In another word, you can use `env` or `arg` to create
`vars`, but not the opposite way.

`env` however, can be defined also in the system scope, so it has the
highest rank in the precedence. So, you shouldn't define a `env` that
depends on a variable defined by `vars` or `args`. If you need to set
your environment variable with a value from a `vars` or `args`, you
should do it in the `run` section.

In the following example, it shows a correct way to use all the
different options of variables, respecting the scopes and rendering order:

```yaml
...
env:
  MY_GLOBAL_ENV: 1
vars:
  MY_GLOBAL_VAR: "my global env is {% raw %}{{ env.MY_GLOBAL_ENV }}{% endraw %}"

groups:
  group1:
    help: "group"
    env:
      MY_GROUP_ENV: 2
    vars:
      MY_GROUP_VAR: "my group env is {% raw %}{{ env.MY_GROUP_ENV }}{% endraw %}"
    targets:
      target1:
        help: "target 1"
        env:
          MY_TARGET_ENV: 3
        args:
          my-target-arg:
            help: "target arg"
            type: string
            default: "{% raw %}{{ env.MY_TARGET_ENV }}{% endraw %}"
        vars:
          MY_TARGET_VAR: "my group env is {% raw %}{{ env.MY_GROUP_ENV }}{% endraw %}"
        run: |
          echo "{% raw %}{{ env.MY_GLOBAL_ENV}}{% endraw %}"
          echo "{% raw %}{{ env.MY_GLOBAL_VAR}}{% endraw %}"
          echo "{% raw %}{{ env.MY_GROUP_ENV}}{% endraw %}"
          echo "{% raw %}{{ env.MY_GROUP_VAR}}{% endraw %}"
          echo "{% raw %}{{ env.MY_TARGET_ENV}}{% endraw %}"
          echo "{% raw %}{{ env.MY_TARGET_VAR}}{% endraw %}"
          echo "{% raw %}{{ env.my_target_arg}}{% endraw %}"
```
