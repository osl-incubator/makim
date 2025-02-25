# Installation

## Stable Release

To install Makim, run the following command in your terminal:

```bash
$ pip install makim
```

Makim is also available on conda-forge:

```bash
$ conda install -c conda-forge makim
```

These installation methods will always provide you with the most recent stable
release.

Additionally, an executable version of Makim is available for Linux x86-64. The
download links for the executables are provided with each new GitHub Release,
for example:
[makim-linux-x86-64 v1.23.1](https://github.com/osl-incubator/makim/releases/download/1.23.1/makim-linux-x86-64).

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
