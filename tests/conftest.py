#!/usr/bin/env python3
# micropipenv
# Copyright(C) 2020 Red Hat, Inc.
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
# type: ignore
"""Configure tests for micropipenv."""

import pytest
import os
from tempfile import TemporaryDirectory

try:
    from pytest_venv import VirtualEnvironment
except ImportError:
    VirtualEnvironment = None

from packaging.version import Version

# Version of pip to test micropipenv with
# the default is the pip wheel bundled in virtualenv package
MICROPIPENV_TEST_PIP_VERSION = os.getenv("MICROPIPENV_TEST_PIP_VERSION")
# pip version used in tests, assigned using pytest_configure
PIP_VERSION = None


def _venv_install_pip(venv):
    """Install pip into the given virtual environment, considering pip version configuration."""
    if MICROPIPENV_TEST_PIP_VERSION is not None:
        if MICROPIPENV_TEST_PIP_VERSION == "latest":
            # This special value always forces the most recent pip version.
            venv.install("pip", upgrade=True)
        elif MICROPIPENV_TEST_PIP_VERSION == "git":
            venv.install("git+https://github.com/pypa/pip.git")
        else:
            venv.install(f"pip{MICROPIPENV_TEST_PIP_VERSION}")


def pytest_configure(config):
    """Configure tests before pytest collects tests."""
    global PIP_VERSION

    if VirtualEnvironment is None:
        # No pip version detection.
        return

    with TemporaryDirectory() as tmp_dir:
        venv = VirtualEnvironment(str(tmp_dir))
        venv.create()
        _venv_install_pip(venv)
        PIP_VERSION = Version(str(venv.get_version("pip")))
        print("The tests will be executed with pip in version: ", PIP_VERSION)


@pytest.fixture(name="venv")
def venv_with_pip():
    """Fixture for virtual environment with specific version of pip.

    Fixture uses the original one from pytest_venv,
    installs pip if MICROPIPENV_TEST_PIP_VERSION is given
    and overwrites the original fixture name
    """
    if VirtualEnvironment is None:
        return pytest.skip("pytest-venv not installed")

    with TemporaryDirectory() as tmp_dir:
        venv = VirtualEnvironment(str(tmp_dir))
        venv.create()
        _venv_install_pip(venv)
        yield venv
