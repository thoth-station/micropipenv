µPipenv
-------

A lightweight wrapper for pip to support Pipenv files or converting them to
pip-tools compatible output.


micropipenv use cases
=====================

Why should I use ``micropipenv`` instead of `Pipenv <https://github.com/pypa/pipenv>`_?

* I would like to convert files produced by Pipenv to a pip-tools compatible
  output.

* I don't want to install Pipenv, but I would like to run a project that uses
  Pipenv for dependency management (e.g. restricted environments).

* My Pipenv installation is broken and `Pipenv upstream did not issue any new
  Pipenv release <https://github.com/pypa/pipenv/issues/4058>`_ - see also
  `Thoth's Pipenv release <https://pypi.org/project/thoth-pipenv>`_ for
  possible fix.

* I would like to deploy my application into a production environment and my
  application dependencies are managed by Pipenv (dependencies are already
  resolved), but I don't want to run Pipenv in production (e.g. OpenShift's s2i
  build process).


``micropipenv install``
=======================

You can install dependencies found in ``Pipfile.lock`` by issuing:

.. code-block:: console

  micropipenv install --dev  # --dev is optional

``micropipenv`` does not create any virtual environment as in case of Pipenv.
It rather directly talks to ``pip``, if necessary, and constructs arguments for
it out of ``Pipfile.lock`` file.

To create a virtual environment to be used by ``micropipenv``:

.. code-block:: console

  python3 -m venv venv/ && . venv/bin/activate


If you wish to mimic ``pipenv --deploy`` functionality, you can do so:

.. code-block:: console

  micropipenv install --deploy

Note however, there is a need to parse ``Pipfile`` and verify its content
corresponds to Pipefile.lock used (digest computed on ``Pipfile`` content).
``micropipenv`` requires toml extras for this functionality, so you will need
to install ``micropipenv[toml]`` (see installation instructions bellow).

You can supply additional positional arguments that will be passed to ``pip``.
Use double dashes to distinguish ``pip`` options from ``micropipenv`` options.

.. code-block::

  # issue `pip install --user'
  micropipenv install -- --user

See ``micropipenv install --help`` for more info.


``micropipenv requirements`` / ``micropipenv req``
==================================================

To generate output compatible with `pip-tools
<https://pypi.org/project/pip-tools/>`_, you can issue the following command:

.. code-block:: console

  micropipenv requirements

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


See ``micropipenv requirements --help`` for more info.


``micropipenv`` as a library
============================

``micropipenv`` exposes some core functionality on top of
``Pipfile``/``Pipfile.lock``.  You can import its functions and use
``micropipenv`` as a lightweight library for ``Pipfile``/``Pipfile.lock``
manipulation.


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


Installation
============

The project is `hosted on PyPI <https://pypi.org/project/micropipenv>`_ so
installing it using ``pip`` works as expected:

.. code-block:: console

  pip install micropipenv

The default installation does no bring any dependencies so its just
``micropipenv`` that gets installed. However, the default installation supports
only ``Pipfile.lock`` management. If you would like to manipulate also with
``Pipfile`` you will need to install ``micropipenv`` with TOML support (TOML is
not in the standard Python library):

.. code-block:: console

  pip install micropipenv[toml]

Once the project gets installed, you can browse the help message by invoking
the ``micropipenv`` CLI:

.. code-block:: console

  micropipenv --help


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
