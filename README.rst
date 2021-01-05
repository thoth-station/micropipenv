µPipenv
-------

.. image:: https://img.shields.io/github/v/tag/thoth-station/micropipenv?style=plastic
  :target: https://github.com/thoth-station/micropipenv/releases
  :alt: GitHub tag (latest by date)

.. image:: https://travis-ci.com/thoth-station/micropipenv.svg?branch=master
  :target: https://travis-ci.com/thoth-station/micropipenv

.. image:: https://img.shields.io/pypi/pyversions/micropipenv?style=plastic
  :target: https://pypi.org/project/micropipenv
  :alt: PyPI - Python Version

.. image:: https://img.shields.io/pypi/l/micropipenv?style=plastic
  :target: https://pypi.org/project/micropipenv
  :alt: PyPI - License

.. image:: https://img.shields.io/pypi/dm/micropipenv?style=plastic
  :target: https://pypi.org/project/micropipenv
  :alt: PyPI - Downloads

A lightweight wrapper for pip to support requirements.txt, Pipenv and Poetry
lock files or converting them to `pip-tools
<https://pypi.org/project/pip-tools/>`_ compatible output. Designed for
containerized Python applications but not limited to them.

For a brief video preview, `check this demo
<https://www.youtube.com/watch?v=I-QC83BcLuo&t=8m58s>`_ (the micropipenv
part starts at 9:00) or this
`blog post <https://medium.com/swlh/a-bridge-to-two-python-dependency-pinning-worlds-micropipenv-5da674f38e89>`_.

To `check S2I integration and best practices for managing Python dependencies
see this blog post
<https://towardsdatascience.com/micropipenv-best-practices-for-installing-python-dependencies-72203925eb0d>`__.

What's the difference in comparision to pip when using requirements.txt?
=========================================================================

* if ``requirements.txt`` state all the packages in a pinned version with
  hashes (e.g. `pip-tools <https://pypi.org/project/pip-tools/>`_), micropipenv
  installs packages with a possible fallback if the installation order is
  relevant

  * you don't need to care about the installation and maintain correct order or
    requirements in ``requirements.txt``

  * best effort installation - try until there is a possibility to succeed

* if ``requirements.txt`` do not state all the packages in a pinned form

  * pip's resolver algorithm is used and it's left on pip to resolve
    requirements

  * the same behavior as micropipenv would not be used


What's the difference in comparision to Poetry?
===============================================

* a lightweight addition to Poetry, not a Poetry replacement

  * micropipenv does not substitute Poetry it rather complements it for
    containerized deployments where the size of the container image and
    software shipped with it matters

* no release management to Python package indexes

* micropipenv does not implement resolver, it uses already resolved stack that
  application is shipped with based on ``poetry.lock`` and ``pyproject.toml``

* no virtual environment management

  * virtual environment management is left on user, if needed

What's the difference in comparision to Pipenv?
===============================================

* a lightweight addition to Pipenv, not a Pipenv replacement

  * micropipenv does not substitute Pipenv it rather complements it for
    containerized deployments where the size of the container image and
    software shipped with it matters

* it does not `vendor all the dependencies as Pipenv
  <https://github.com/pypa/pipenv/tree/master/pipenv/vendor>`_

* micropipenv does not implement resolver, it uses already resolved stack that
  application is shipped with ``Pipfile.lock``

* no virtual environment management

  * virtual environment management is left on user, if needed

micropipenv use cases
=====================

Why should I use ``micropipenv`` instead of `Pipenv <https://github.com/pypa/pipenv>`_
or `Poetry <https://pypi.org/project/poetry>`_?

* I would like to have a tool that "rules them all" - one lightweight tool to
  support all Python dependency lock file managers (pip-tools, Poetry, Pipenv)
  and lets users decide what they want to use when deploying Python applications
  in containerized environments (e.g. Kubernetes, OpenShift, ...)

* I would like to have containerized Python applications as small as possible
  with minimum software shipped and required to build and run the Python
  application in production.

* I would like to convert files produced by Pipenv/Poetry to a pip-tools
  compatible output.

* I don't want to install Pipenv/Poetry, but I would like to run a project that
  uses Pipenv/Poetry for dependency management (e.g. restricted environments).

* My Pipenv installation is broken and `Pipenv upstream did not issue any new
  Pipenv release <https://github.com/pypa/pipenv/issues/4058>`_

* I would like to deploy my application into a production environment and my
  application dependencies are managed by Pipenv/Poetry (dependencies are
  already resolved), but I don't want to run Pipenv/Poetry in production (e.g.
  OpenShift's s2i build process).


``micropipenv install``
=======================

The tool supports installing dependencies of the following formats:

* ``Pipenv`` style lock format - files ``Pipfile`` and ``Pipfile.lock``
* ``Poetry`` style lock format - files ``pyproject.toml`` and ``poetry.lock``
* ``pip-tools`` style lock format - file ``requirements.txt``
* raw ``requirements.txt`` as used by ``pip`` (not a lock file)

In case of Pipenv, Poetry and pip-tools style format, the tool performs
automatic recovery if the installation order of dependencies is relevant (one
dependency fails to install as it depends on an another one).

To enforce the installation method used, specify ``--method`` option to the
``install`` subcommand. By default, ``micropipenv`` traverses the filesystem up
from the current working directory and looks for the relevant files in the
following order:

1. ``Pipfile.lock`` and optionally ``Pipfile`` (if ``--deploy`` set)
2. ``poetry.lock`` and ``pyproject.toml``
3. ``requirements.txt`` for ``pip-tools`` and raw ``pip`` requirements

To install dependencies issue the following command:

.. code-block:: console

  micropipenv install --dev  # --dev is optional

You can supply additional positional arguments that will be passed to ``pip``.
Use double dashes to distinguish ``pip`` options from ``micropipenv`` options.

.. code-block::

  # issue `pip install --user'
  micropipenv install -- --user

``micropipenv`` does not create any virtual environment as in case of
Pipenv/Poetry.  It rather directly talks to ``pip``, if necessary, and
constructs arguments out of the lock file used.

To create a virtual environment to be used by ``micropipenv``:

.. code-block:: console

  python3 -m venv venv/ && . venv/bin/activate


``micropipenv install --deploy``
================================

If you wish to mimic ``pipenv --deploy`` functionality, you can do so:

.. code-block:: console

  micropipenv install --deploy

Note however, there is a need to parse ``Pipfile`` and verify its content
corresponds to Pipefile.lock used (digest computed on ``Pipfile`` content).
``micropipenv`` requires toml extras for this functionality, so you will need
to install ``micropipenv[toml]`` (see installation instructions bellow).

The ``--deploy`` option takes no effect for Poetry and requirements
installation methods.


``micropipenv install --dev``
================================

Installation of "development" dependnecies can be acomplished using the
``--dev`` flag. This flag has no effect when ``requirements.txt`` file is used.


``micropipenv requirements`` / ``micropipenv req``
==================================================

To generate output compatible with `pip-tools
<https://pypi.org/project/pip-tools/>`_, you can issue the following command:

.. code-block:: console

  micropipenv requirements

This applies to conversion from Poetry and Pipenv specific lock files.

Additional configuration options can limit what is present in the output (e.g.
``--no-dev`` to remove development dependencies).

A special option ``--only-direct`` makes ``micropipenv`` work on ``Pipfile``
instead of ``Pipfile.lock``. This requires toml extras, so install
``micropipenv[toml]`` for this functionality (see installation instructions
bellow). To get direct dependencies of an application and store them in
requirements.txt file:

.. code-block:: console

  micropipenv requirements --only-direct > requirements.txt


For a setup that follows ``pip-tools`` convention with ``requirements.in`` and
``requirements.txt``

.. code-block:: console

  micropipenv requirements --no-dev > requirements.txt
  micropipenv requirements --no-dev --only-direct > requirements.in
  micropipenv requirements --no-default > dev-requirements.txt
  micropipenv requirements --no-default --only-direct > dev-requirements.in


See ``micropipenv requirements --help`` for more info.


``micropipenv`` as a library
============================

``micropipenv`` exposes some core functionality on top of
``Pipfile``/``Pipfile.lock``.  You can import its functions and use
``micropipenv`` as a lightweight library for ``Pipfile``/``Pipfile.lock`` and
``pyproject.toml``/``poetry.lock`` manipulation.


Adjusting options using environment variables
=============================================

All options can be triggered using environment variables - the name of an
environment variable is always prefixed with ``MICROPIPENV_`` and consists of
the name of the option converted to uppercase, dashes are replaced with
underscores (example ``--no-dev`` is mapped to ``MICROPIPENV_NO_DEV``). All
environment variables corresponding to flags are parsed as integers and
subsequently casted to a boolean. For example, to turn ``--no-dev`` flag on,
set ``MICROPIPENV_NO_DEV=1`` (0 disables the flag). Parameters supplied to CLI
take precedence over environment variables.

A special environment variable ``MICROPIPENV_PIP_BIN`` can point to an
alternate ``pip`` binary.

To run this tool in a verbose mode, you can set the ``MICROPIPENV_DEBUG=1`` (the
same behavior can be achieved with multiple ``--verbose`` supplied).

The tool prints software stack information to the standard error output. This was
designed for Thoth to capture information about installed dependencies as a
useful source of information for Thoth's build analyzers. This behaviour can be
suppressed by setting ``MICROPIPENV_NO_LOCKFILE_PRINT=1`` environment variable.

Besides printing, the tool also writes the content of Pipfile.lock (if a locked
software stack is used) to the directory where lock files are present (for Pipenv
files, the Pipfile.lock is kept untouched). This behaviour can be suppressed by
providing ``MICROPIPENV_NO_LOCKFILE_WRITE=1`` environment variable.

Example usage
=============

Install dependencies managed by Poetry as ``pip install --user`` would do
(option ``--method`` is optional, auto-discovery is performed if omitted):

.. code-block:: console

  $ ls
  poetry.lock pyproject.toml project.py
  $ micropipenv install --method poetry -- --user

Install dependencies (both main and develop) managed by Poetry into a virtual
environment:

.. code-block:: console

  $ ls
  poetry.lock pyproject.toml project.py
  $ python3 -m venv venv/
  $ . venv/bin/activate
  (venv) $ micropipenv install --dev

Install dependencies managed by Pipenv (both main and develop) into a virtual
environment  (option ``--method`` is optional, auto-discovery is performed if
omitted):

.. code-block:: console

  $ ls
  Pipfile Pipfile.lock src/
  $ python3 -m venv venv/
  $ . venv/bin/activate
  (venv) $ micropipenv install --dev


Perform deployment of an application as Pipenv would do with Python interpreter
version check and Pipfile file hash check (you can create virtual environment
only if necessary):

.. code-block:: console

  $ ls
  Pipfile Pipfile.lock src/
  $ python3 -m venv venv/
  $ . venv/bin/activate
  (venv) $ micropipenv --deploy

Generate `pip-tools <https://pypi.org/project/pip-tools/>`_ compliant
``requirements.in``, ``dev-requirements.in``, ``requirements.txt`` and
``dev-requirements.txt`` out of ``Pipfile`` and ``Pipfile.lock`` - project
dependencies managed by Pipenv:

.. code-block:: console

  $ ls
  Pipfile Pipfile.lock src/
  $ micropipenv requirements --no-dev > requirements.txt
  $ micropipenv requirements --no-dev --only-direct > requirements.in
  $ micropipenv requirements --no-default > dev-requirements.txt
  $ micropipenv requirements --no-default --only-direct > dev-requirements.in

Generate `pip-tools <https://pypi.org/project/pip-tools/>`_ complaint
``requirements.in``, ``dev-requirements.in``, ``requirements.txt`` and
``dev-requirements.txt`` out of ``pyproject.toml`` and ``poetry.lock`` - project
dependencies managed by Poetry:

.. code-block:: console

  $ ls
  poetry.lock pyproject.toml src/
  $ micropipenv requirements --no-dev > requirements.txt
  $ micropipenv requirements --no-dev --only-direct > requirements.in
  $ micropipenv requirements --no-default > dev-requirements.txt
  $ micropipenv requirements --no-default --only-direct > dev-requirements.in

For OpenShift's s2i integration,
`check this repo with a demo <https://github.com/fridex/s2i-example-micropipenv>`_.

Installation
============

The project is `hosted on PyPI <https://pypi.org/project/micropipenv>`_ so
installing it using ``pip`` works as expected:

.. code-block:: console

  pip install micropipenv

The default installation does not bring any dependencies so its just
``micropipenv`` that gets installed. However, the default installation supports
only ``Pipfile.lock`` management. If you would like to manipulate also with
``Pipfile`` or Poetry specific lock files, you will need to install
``micropipenv`` with TOML support (TOML is not in the standard Python library):

.. code-block:: console

  pip install micropipenv[toml]

Once the project gets installed, you can browse the help message by invoking
the ``micropipenv`` CLI:

.. code-block:: console

  micropipenv --help

If you wish to install ``micropipenv`` on your Fedora system:

.. code-block:: console

  dnf install -y micropipenv

See available `RPM packages <https://src.fedoraproject.org/rpms/micropipenv>`_.

No installation
===============

You can run ``micropipenv`` without actually installing it - simply download
the file and execute it. If you do not wish to save ``micropipenv.py`` file to
disk, you can issue:

.. code-block:: console

  curl https://raw.githubusercontent.com/thoth-station/micropipenv/master/micropipenv.py | python3 - --help

Anything after ``python3 -`` will be passed as an argument to
``micropipenv.py`` so installing packages can be simply performed using:

.. code-block:: console

  curl https://raw.githubusercontent.com/thoth-station/micropipenv/master/micropipenv.py | python3 - install -- --user

All arguments after -- will be passed to ``pip`` as options.

OpenShift s2i (Source-To-Image)
===============================

micropipenv is available in UBI, Fedora and RHEL based container images. To
enable micropipenv and benefit from its features, you need to export
``ENABLE_MICROPIPENV=1`` environment variable in more recent Python 3 container
images. See `sclorg/s2i-python-container
<https://github.com/sclorg/s2i-python-container/tree/master/3.8>`__ repo for
more information.

License and copying
===================

This project is licensed under the terms of the GNU Lesser General Public
License v3 or later. See ``LICENSE-LGPL`` and ``LICENSE-GPL`` files for the
license terms.

Copyright (C) 2020 AICoE `Project Thoth <http://thoth-station.ninja/>`__; Red Hat Inc.

Authors and maintainers:
 * Fridolín 'fridex' Pokorný <fridolin@redhat.com>
 * Lumír 'Frenzy' Balhar <lbalhar@redhat.com>
