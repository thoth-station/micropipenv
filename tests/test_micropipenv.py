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

import sys
from contextlib import contextmanager
from contextlib import redirect_stdout
import flexmock
import os
import pytest
import shutil
import subprocess
import json

import micropipenv


_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.relpath(__file__)), "data"))


@contextmanager
def cwd(target):
    """Manage cwd in a pushd/popd fashion."""
    curdir = os.getcwd()
    os.chdir(target)
    try:
        yield curdir
    finally:
        os.chdir(curdir)


def get_pip_path(venv):
    """Get path to pip in a virtual environment used in tests."""
    return os.path.join(venv.path, "bin", "pip3")


def check_generated_pipfile_lock(pipfile_lock_path, pipfile_lock_path_expected):
    """Check generated Pipfile.lock produced during tests."""
    assert os.path.isfile(pipfile_lock_path), "No Pipfile.lock was produced"

    with open(pipfile_lock_path) as f1, open(pipfile_lock_path_expected) as f2:
        pipfile_lock = json.load(f1)
        expected_pipfile_lock = json.load(f2)

    # The actual Python version noted differs based on the environment in which tests were executed in.
    python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
    expected_pipfile_lock["_meta"]["requires"].pop("python_version", None)

    assert pipfile_lock == expected_pipfile_lock
    assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)

    os.remove(pipfile_lock_path)


def test_install_pipenv(venv):
    """Test invoking installation using information in Pipfile.lock."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv)})
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"


def test_install_pipenv_vcs(venv):
    """Test invoking installation using information in Pipfile.lock, a git version is used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_vcs")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv)})
        assert str(venv.get_version("daiquiri")) == "2.0.0"


def test_install_poetry(venv):
    """Test invoking installation using information from a Poetry project."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "poetry"]
    venv.install("toml==0.10.0")
    work_dir = os.path.join(_DATA_DIR, "install", "poetry")
    with cwd(os.path.join(_DATA_DIR, "install", "poetry")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv)})
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


def test_install_poetry_vcs(venv):
    """Test invoking installation using information from a Poetry project, a git version is used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "poetry"]
    venv.install("toml==0.10.0")
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_vcs")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv)})
        assert str(venv.get_version("daiquiri")) == "2.1.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


def test_install_pip_tools_print_lock(venv):
    """Test invoking installation when pip-tools style requirements.txt are used.

    This test uses directly method to verify the lock file is printed.
    """
    work_dir = os.path.join(_DATA_DIR, "install", "pip-tools")
    with cwd(work_dir):
        flexmock(micropipenv).should_receive("_maybe_print_pipfile_lock").once()
        micropipenv.install_requirements(get_pip_path(venv))
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"


def test_install_pip(venv):
    """Test invoking installation when raw requirements.txt are used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv)})
        assert str(venv.get_version("requests")) == "1.0.0"


def test_install_pip_vcs(venv):
    """Test installation of a package from VCS (git)."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements_vcs")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv)})
        assert str(venv.get_version("daiquiri")) == "2.1.0"
        assert str(venv.get_version("python-json-logger")) is not None


def test_install_pip_print_freeze(venv):
    """Test invoking installation when raw requirements.txt are used.

    This test uses directly the installation method to verify pip freeze being printed.
    """
    work_dir = os.path.join(_DATA_DIR, "install", "requirements")
    with cwd(work_dir):
        flexmock(micropipenv).should_receive("_maybe_print_pip_freeze").once()
        micropipenv.install_requirements(get_pip_path(venv))
        assert str(venv.get_version("requests")) == "1.0.0"


def test_method_detection_poetry(tmp_path):
    """Test detecting installation method to be used - Poetry."""
    # Touch files with specific names so that detection can find them.
    with open(os.path.join(tmp_path, "pyproject.toml"), "w"):
        pass

    with open(os.path.join(tmp_path, "poetry.lock"), "w"):
        pass

    work_dir = os.path.join(tmp_path, "poetry")
    os.makedirs(work_dir)
    with cwd(work_dir):
        flexmock(micropipenv).should_receive("install_poetry").once()
        micropipenv.install(method=None)


def test_method_detection_pipenv(tmp_path):
    """Test detecting installation method to be used - Pipenv."""
    with open(os.path.join(tmp_path, "Pipfile.lock"), "w"):
        pass

    work_dir = os.path.join(tmp_path, "pipenv")
    os.makedirs(work_dir)
    with cwd(work_dir):
        flexmock(micropipenv).should_receive("install_pipenv").once()
        micropipenv.install(method=None)


def test_method_detection_requirements(tmp_path):
    """Test detecting installation method to be used - requirements."""
    with open(os.path.join(tmp_path, "requirements.txt"), "w"):
        pass

    work_dir = os.path.join(tmp_path, "requirements")
    os.makedirs(work_dir)
    with cwd(work_dir):
        flexmock(micropipenv).should_receive("install_requirements").once()
        micropipenv.install(method=None)


def test_install_pipenv_deploy_error_python(venv):
    """Test installation error on --deploy set, error because Python version."""
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_error_python")):
        flexmock(micropipenv).should_receive("_maybe_print_pipfile_lock").once()
        err_msg = r"Running Python version \d.\d, but Pipfile.lock requires Python version 5.9"
        with pytest.raises(micropipenv.PythonVersionMismatch, match=err_msg):
            micropipenv.install_pipenv(get_pip_path(venv), deploy=True)


def test_install_pipenv_deploy_error_hash(venv):
    """Test installation error on --deploy set, error because wrong hash in Pipfile.lock."""
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_error_hash")):
        flexmock(micropipenv).should_receive("_maybe_print_pipfile_lock").once()
        err_msg = (
            "Pipfile.lock hash 'foobar' does not correspond to hash computed based "
            "on Pipfile '8b8dfe383cda8e22d95623518c911b7d5cf28acb8fccd4b7d8dc67fce444b6d3', "
            "aborting deployment"
        )
        with pytest.raises(micropipenv.HashMismatch, match=err_msg):
            micropipenv.install_pipenv(get_pip_path(venv), deploy=True)


def test_parse_requirements2pipfile_lock():
    """Test parsing of requirements.txt into their Pipfile.lock representation."""
    work_dir = os.path.join(_DATA_DIR, "parse", "pip-tools")
    with cwd(work_dir):
        pipfile_lock = micropipenv._requirements2pipfile_lock()

        with open("Pipfile.lock") as f:
            expected_pipfile_lock = json.load(f)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        expected_pipfile_lock["_meta"]["requires"].pop("python_version", None)
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)
        assert pipfile_lock == expected_pipfile_lock


def test_parse_requirements2pipfile_lock_not_locked():
    """Test raising an exception when requirements.txt do not state all packages as locked."""
    work_dir = os.path.join(_DATA_DIR, "parse", "requirements")
    with cwd(work_dir):
        with pytest.raises(micropipenv.PipRequirementsNotLocked):
            micropipenv._requirements2pipfile_lock()


def test_parse_poetry2pipfile_lock():
    """Test parsing Poetry specific files into Pipfile.lock representation."""
    work_dir = os.path.join(_DATA_DIR, "parse", "poetry")
    with cwd(work_dir):
        pipfile_lock = micropipenv._poetry2pipfile_lock()
        with open("Pipfile.lock") as f:
            expected_pipfile_lock = json.load(f)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        expected_pipfile_lock["_meta"]["requires"].pop("python_version", None)
        assert pipfile_lock == expected_pipfile_lock
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)


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


def test_main_install_params_default():
    """Test running install from main with default parameters set."""
    flexmock(micropipenv).should_receive("install").with_args(deploy=True, dev=True, pip_args=[], method=None).once()
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
