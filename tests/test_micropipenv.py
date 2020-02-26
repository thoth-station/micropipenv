#!/usr/bin/env python3
# micropipenv
# Copyright(C) 2020 Fridolin Pokorny
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

"""Testsuite for micropipenv."""

from contextlib import contextmanager
from contextlib import redirect_stdout
import flexmock
import os
import pytest
import shutil
import subprocess

import micropipenv


_DATA_DIR = os.path.join(os.path.dirname(os.path.relpath(__file__)), "data")


@contextmanager
def cwd(target):
    """Manage cwd in a pushd/popd fashion."""
    curdir = os.getcwd()
    os.chdir(target)
    try:
        yield curdir
    finally:
        os.chdir(curdir)


def test_install(venv):
    """Test invoking installation using information in Pipfile.lock."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install"]
    with cwd(os.path.join(_DATA_DIR, "install", "venv_install")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": os.path.join(venv.path, "bin", "pip3")})
        assert str(venv.get_version("daiquiri")) == "2.0.0"


def test_install_deploy_error_python():
    """Test installation error on --deploy set, error because Python version."""
    with cwd(os.path.join(_DATA_DIR, "install", "error_python")):
        err_msg = r"Running Python version \d.\d, but Pipfile.lock requires Python version 5.9"
        with pytest.raises(micropipenv.PythonVersionMismatch, match=err_msg):
            micropipenv.install(deploy=True)


def test_install_deploy_error_hash():
    """Test installation error on --deploy set, error because wrong hash in Pipfile.lock."""
    with cwd(os.path.join(_DATA_DIR, "install", "error_hash")):
        err_msg = (
            "Pipfile.lock hash 'foobar' does not correspond to hash computed based "
            "on Pipfile '70e8bf6bc774f5ca177467cab4e67d4264d0536857993326abc13ff43063bec0', "
            "aborting deployment"
        )
        with pytest.raises(micropipenv.HashMismatch, match=err_msg):
            micropipenv.install(deploy=True)


@pytest.mark.parametrize(
    "test,options,expected_file",
    [
        ("default", {"no_comments": True}, "requirements_no_comments.txt"),
        ("default", {"no_default": True}, "requirements_no_default.txt"),
        ("default", {"no_dev": True}, "requirements_no_dev.txt"),
        ("default", {"no_hashes": True}, "requirements_no_hashes.txt"),
        ("default", {"no_indexes": True}, "requirements_no_indexes.txt"),
        ("default", {"no_versions": True}, "requirements_no_versions.txt"),
        ("default", {"only_direct": True}, "requirements_only_direct.txt"),
        ("dev", {"no_comments": True}, "requirements_no_comments.txt"),
        ("dev", {"no_default": True}, "requirements_no_default.txt"),
        ("dev", {"no_dev": True}, "requirements_no_dev.txt"),
        ("dev", {"no_hashes": True}, "requirements_no_hashes.txt"),
        ("dev", {"no_indexes": True}, "requirements_no_indexes.txt"),
        ("dev", {"no_versions": True}, "requirements_no_versions.txt"),
        ("dev", {"only_direct": True}, "requirements_only_direct.txt"),
        ("extras", {"no_comments": True}, "requirements_no_comments.txt"),
        ("extras", {"no_default": True}, "requirements_no_default.txt"),
        ("extras", {"no_dev": True}, "requirements_no_dev.txt"),
        ("extras", {"no_hashes": True}, "requirements_no_hashes.txt"),
        ("extras", {"no_indexes": True}, "requirements_no_indexes.txt"),
        ("extras", {"no_versions": True}, "requirements_no_versions.txt"),
        ("extras", {"only_direct": True}, "requirements_only_direct.txt"),
        ("source", {"no_comments": True}, "requirements_no_comments.txt"),
        ("source", {"no_default": True}, "requirements_no_default.txt"),
        ("source", {"no_dev": True}, "requirements_no_dev.txt"),
        ("source", {"no_hashes": True}, "requirements_no_hashes.txt"),
        ("source", {"no_indexes": True}, "requirements_no_indexes.txt"),
        ("source", {"no_versions": True}, "requirements_no_versions.txt"),
        ("source", {"only_direct": True}, "requirements_only_direct.txt"),
        ("extras_marker", {"no_comments": True}, "requirements_no_comments.txt"),
        ("extras_marker", {"no_default": True}, "requirements_no_default.txt"),
        ("extras_marker", {"no_dev": True}, "requirements_no_dev.txt"),
        ("extras_marker", {"no_hashes": True}, "requirements_no_hashes.txt"),
        ("extras_marker", {"no_indexes": True}, "requirements_no_indexes.txt"),
        ("extras_marker", {"no_versions": True}, "requirements_no_versions.txt"),
        ("extras_marker", {"only_direct": True}, "requirements_only_direct.txt"),
    ],
)
def test_requirements(tmp_path, test, options, expected_file):
    """Test generating requirements out of Pipfile and Pipfile.lock."""
    shutil.copyfile(os.path.join(_DATA_DIR, "requirements", test, "Pipfile"), os.path.join(tmp_path, "Pipfile"))
    shutil.copyfile(
        os.path.join(_DATA_DIR, "requirements", test, "Pipfile.lock"), os.path.join(tmp_path, "Pipfile.lock")
    )
    expected_output_file_path = os.path.join(_DATA_DIR, "requirements", test, expected_file)
    with open(expected_output_file_path, "r") as f:
        expected = f.read()

    with cwd(tmp_path):
        with open("output.txt", "w") as f, redirect_stdout(f):
            micropipenv.requirements(**options)
        with open("output.txt", "r") as f:
            assert f.read() == expected


def test_main_install_params():
    """Test running install from main with default parameters set."""
    flexmock(micropipenv).should_receive("install").with_args(deploy=True, dev=True, pip_args=[]).once()
    micropipenv.main(argv=["install", "--deploy", "--dev"])


def test_main_requirements_params():
    """Test running install from main with default parameters set."""
    flexmock(micropipenv).should_receive("requirements").with_args(
        no_hashes=False,
        no_indexes=False,
        no_versions=False,
        only_direct=True,
        no_default=False,
        no_dev=False,
        no_comments=True,
    ).once()

    micropipenv.main(argv=["requirements", "--only-direct", "--no-comments"])
