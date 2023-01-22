# makim

Simplify the usage of containers.

You may be thinking, why do I need a new library that wrap-up
docker-compose or podman-compose if they are already really simple to use?

Yes, they are simple to use, but if you have some other parameters to
the compose command line, it could be very tedious to write them every time
such as `--env-file`, `--project-name`, `--file`, etc.

So, in this case we could use something like a script or `make`, right?

Yes, and just for one project it would be good enough. But, if you maintain
or collaborate a bunch of projects, it would be like a boiler plate.

Additionally, if you are maintaining some extra scripts in order to improve
your containers stack, these scripts would be like a boilerplate as well.

So, the idea of this project is to organize your stack of containers,
gathering some useful scripts and keeping this information centralized in a
configuration file. So the command line would be very simple.


* Free software: BSD 3 Clause
* Documentation: https://osl-incubator.github.io/makim


## Features


The commands availables now are:
  `help`, `version`, `build`, `down`, `get-ip`,
  `logs`, `logs-follow`, `pull`, `restart`,
  `start`, `stop`, `wait`.

> Note: `get-ip` and `wait` are not yet implemented.


## How to use it

First you need to place the config file `.makim.yaml` in the root of your project. This is an example of a configuration file:

```yaml
version: 1.0.0
compose-app: docker-compose
service-groups:
  - name: group1
    project-name: project1  # optional
    compose-path: containers/tests/group1/compose.yaml
    env-file: .env
    services:
      default: service1,service3
      list:
        - name: service1
          health-check: true
        - name: service2
          health-check: false
        - name: service3
          health-check: true
  - name: group2
    project-name: null  # optional
    compose-path: containers/tests/group2/compose.yaml
    env-file: .env
    services:
      default: null
      list:
        - name: service1
          health-check: true
        - name: service1
          health-check: false
```


Some examples of how to use it:

* build the defaults services (service1,service3) for group1:
  `makim build --group group1`

* build the all services (there is no default service defined) for group2:
  `makim build --group group2`

* build all services (ignore default) for group1:
  `makim build --group group1 --service ""`

* start the default services for group1:
  `makim start --group group1`

* restart all services (ignore defaults) for group1:
  `makim restart --group group1 --service ""`

* restart service1 and service2 for group1:
  `makim restart --group group1 --service service1,service2`
