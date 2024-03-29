# Installation

## Stable release

To install makim, run this command in your terminal:

```bash
$ pip install makim
```

Makim is also available on conda-forge:

```bash
$ conda install -c conda-forge makim
```

This is the preferred method to install makim, as it will always install the
most recent stable release.

## From sources

The sources for makim can be downloaded from the
[Github repo](https://github.com/osl-incubator/makim.git).

You can either clone the public repository:

```bash
$ git clone https://github.com/osl-incubator/makim.git
```

Or download the
[tarball](https://github.com/osl-incubator/makim.git/tarball/main):

```bash
$ curl -OJL https://github.com/osl-incubator/makim.git/tarball/main
```

Once you have a copy of the source, change to the project root directory and
install it with:

```bash
$ poetry install
```

PS: You need to have poetry installed. You can use it also from a conda
environment. Check the `Contributing` page for more information.
