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

import glob
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

from conftest import PIP_VERSION


_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.relpath(__file__)), "data"))
# Implementation of `toml` to test micropipenv with
MICROPIPENV_TEST_TOML_MODULE = os.getenv("MICROPIPENV_TEST_TOML_MODULE", "toml")


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


def setup_module():
    """Dirty hack for mypy that does not accept collisions in file names."""
    for item in glob.glob(os.path.join(_DATA_DIR, "**", "setup"), recursive=True):
        shutil.copyfile(item, "{}.py".format(item))

    for item in glob.glob(os.path.join(_DATA_DIR, "**", "main"), recursive=True):
        shutil.copyfile(item, "{}.py".format(item))


def teardown_module():
    """Recover from the dirty hack for mypy."""
    for item in glob.glob(os.path.join(_DATA_DIR, "**", "setup.py"), recursive=True):
        os.remove(item)

    for item in glob.glob(os.path.join(_DATA_DIR, "**", "main.py"), recursive=True):
        os.remove(item)


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


@pytest.mark.online
def test_install_pipenv(venv):
    """Test invoking installation using information in Pipfile.lock."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"


@pytest.mark.online
def test_install_pipenv_vcs(venv):
    """Test invoking installation using information in Pipfile.lock, a git version is used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_vcs")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("daiquiri")) == "2.0.0"


@pytest.mark.online
def test_install_pipenv_file(venv):
    """Test invoking installation using information in Pipfile.lock, a file mode is used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_file")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"


@pytest.mark.online
def test_install_pipenv_editable(venv):
    """Test invoking installation using information in Pipfile.lock, an editable mode is used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_editable")):
        try:
            subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
            assert str(venv.get_version("daiquiri")) == "2.0.0"
            assert str(venv.get_version("python-json-logger")) == "0.1.11"
            assert str(venv.get_version("micropipenv-editable-test")) == "1.2.3"
            assert (
                len(
                    glob.glob(
                        os.path.join(venv.path, "lib", "python*", "site-packages", "micropipenv-editable-test.egg-link")
                    )
                )
                == 1
            ), "No egg-link found for editable install"
        finally:
            # Clean up this file, can cause issues across multiple test runs.
            shutil.rmtree("micropipenv_editable_test.egg-info", ignore_errors=True)


@pytest.mark.online
def test_install_pipenv_vcs_editable(venv):
    """Test invoking installation using information in Pipfile.lock, a git version in editable mode is used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_vcs_editable")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("daiquiri")) == "1.6.0"
        assert (
            len(glob.glob(os.path.join(venv.path, "lib", "python*", "site-packages", "daiquiri.egg-link"))) == 1
        ), "No egg-link found for editable install"


@pytest.mark.online
def test_install_poetry(venv):
    """Test invoking installation using information from a Poetry project."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "poetry"]
    venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry")
    with cwd(os.path.join(_DATA_DIR, "install", "poetry")):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
def test_install_poetry_vcs(venv):
    """Test invoking installation using information from a Poetry project, a git version is used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "poetry"]
    venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_vcs")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("daiquiri")) == "2.1.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
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


@pytest.mark.online
def test_install_pip(venv):
    """Test invoking installation when raw requirements.txt are used."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("requests")) == "1.0.0"


@pytest.mark.online
def test_install_pip_vcs(venv):
    """Test installation of a package from VCS (git)."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements_vcs")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("daiquiri")) == "2.1.0"
        assert str(venv.get_version("python-json-logger")) is not None


@pytest.mark.online
def test_install_pip_editable(venv):
    """Test installation of an editable package which is not treated as a lock file."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements_editable_unlocked")
    with cwd(work_dir):
        try:
            subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
            assert str(venv.get_version("micropipenv-editable-test")) == "3.3.3"
            assert (
                len(
                    glob.glob(
                        os.path.join(venv.path, "lib", "python*", "site-packages", "micropipenv-editable-test.egg-link")
                    )
                )
                == 1
            ), "No egg-link found for editable install"
            assert str(venv.get_version("q")) == "1.0"
        finally:
            # Clean up this file, can cause issues across multiple test runs.
            shutil.rmtree("micropipenv_editable_test.egg-info", ignore_errors=True)


@pytest.mark.online
def test_install_pip_tools_editable(venv):
    """Test installation of an editable package."""
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements_editable")
    with cwd(work_dir):
        try:
            subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
            assert str(venv.get_version("micropipenv-editable-test")) == "3.2.1"
            assert (
                len(
                    glob.glob(
                        os.path.join(venv.path, "lib", "python*", "site-packages", "micropipenv-editable-test.egg-link")
                    )
                )
                == 1
            ), "No egg-link found for editable install"
            assert str(venv.get_version("daiquiri")) == "2.0.0"
            assert str(venv.get_version("python-json-logger")) == "0.1.11"
        finally:
            # Clean up this file, can cause issues across multiple test runs.
            shutil.rmtree("micropipenv_editable_test.egg-info", ignore_errors=True)


@pytest.mark.online
@pytest.mark.skipif(
    PIP_VERSION is not None and PIP_VERSION.release < (19, 3, 0),
    reason="Direct reference installation is supported in pip starting 19.3",
)
def test_install_pip_tools_direct_reference(venv):
    """Test installation of a direct reference.

    See https://pip.pypa.io/en/stable/reference/pip_install/#requirement-specifiers
    """
    cmd = [os.path.join(venv.path, "bin", "python3"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "pip-tools_direct_reference")
    with cwd(work_dir):
        with open("requirements.txt", "w") as requirements_file:
            artifact_path = os.path.join(os.getcwd(), "micropipenv-0.0.0.tar.gz")
            requirements_file.write(
                "micropipenv @ file://{} --hash=sha256:03b3f06d0e3c403337c73d8d95b1976449af8985e40a6aabfd9620c282c8d060\n".format(
                    artifact_path
                )
            )

        subprocess.run(cmd, check=True, env={"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
        assert str(venv.get_version("micropipenv")) == "0.0.0"


@pytest.mark.online
def test_install_pip_print_freeze(venv):
    """Test invoking installation when raw requirements.txt are used.

    This test uses directly the installation method to verify pip freeze being printed.
    """
    work_dir = os.path.join(_DATA_DIR, "install", "requirements")
    with cwd(work_dir):
        flexmock(micropipenv).should_receive("_maybe_print_pip_freeze").once()
        micropipenv.install_requirements(get_pip_path(venv))
        assert str(venv.get_version("requests")) == "1.0.0"


def test_install_pip_svn(venv):
    """Test installation of a package from VCS (git)."""
    work_dir = os.path.join(_DATA_DIR, "install", "requirements_svn")
    with cwd(work_dir), pytest.raises(
        micropipenv.NotSupportedError,
        match=r"Non-Git VCS requirement 'svn\+svn://svn.repo/some_pkg/trunk/#egg=SomePackage' is not supported yet",
    ):
        micropipenv.install_requirements(get_pip_path(venv))


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
        err_msg = r"Running Python version \d+.\d+, but Pipfile.lock requires Python version 5.9"
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


@pytest.mark.online
def test_install_pipenv_iter_index(venv):
    """Test triggering multiple installations if index is not explicitly set to one."""
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_iter_index")):
        micropipenv.install_pipenv(get_pip_path(venv), deploy=False)
        assert str(venv.get_version("requests")) == "1.0.0"


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


def test_parse_pipenv2pipfile_lock_only_direct():
    """Test parsing Pipfile and obtaining direct dependencies out of it."""
    work_dir = os.path.join(_DATA_DIR, "parse", "pipenv")
    with cwd(work_dir):
        pipfile_lock = micropipenv.get_requirements_sections(only_direct=True)

        assert pipfile_lock == {
            "default": {"daiquiri": {"version": "==2.0.0"}},
            "develop": {"flexmock": {"version": "*"}},
            "sources": [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True}],
        }


def test_parse_pipenv2pipfile_lock_only_direct_no_default():
    """Test parsing Pipfile and obtaining direct dependencies out of it."""
    work_dir = os.path.join(_DATA_DIR, "parse", "pipenv")
    with cwd(work_dir):
        pipfile_lock = micropipenv.get_requirements_sections(only_direct=True, no_default=True)

        assert pipfile_lock == {
            "default": {},
            "develop": {"flexmock": {"version": "*"}},
            "sources": [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True}],
        }


def test_parse_pipenv2pipfile_lock_only_direct_no_dev():
    """Test parsing Pipfile and obtaining direct dependencies out of it."""
    work_dir = os.path.join(_DATA_DIR, "parse", "pipenv")
    with cwd(work_dir):
        pipfile_lock = micropipenv.get_requirements_sections(only_direct=True, no_dev=True)

        assert pipfile_lock == {
            "develop": {},
            "default": {"daiquiri": {"version": "==2.0.0"}},
            "sources": [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True}],
        }


def test_parse_pipenv2pipfile_lock_no_default():
    """Test parsing Pipfile and obtaining only dev dependencies."""
    work_dir = os.path.join(_DATA_DIR, "parse", "pipenv")
    with cwd(work_dir):
        pipfile_lock = micropipenv.get_requirements_sections(
            no_default=True,
        )

        assert pipfile_lock == {
            "default": {},
            "develop": {
                "flexmock": {
                    "hashes": ["sha256:5033ceb974d6452cf8716c2ff5059074b77e546df5c849fb44a53f98dfe0d82c"],
                    "index": "pypi",
                    "version": "==0.10.4",
                }
            },
            "sources": [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True}],
        }


def test_parse_pipenv2pipfile_lock_no_dev():
    """Test parsing Pipfile.lock and obtaining only default dependencies."""
    work_dir = os.path.join(_DATA_DIR, "parse", "pipenv")
    with cwd(work_dir):
        pipfile_lock = micropipenv.get_requirements_sections(
            no_dev=True,
        )

        assert pipfile_lock == {
            "default": {
                "daiquiri": {
                    "hashes": [
                        "sha256:6b235ed15b73b87fd3cc2521aacbb727bf8443a0896dc534b07503841d03cfdb",
                        "sha256:d57b9fd5432933c6e899054eb62cee22eab89f560c8493254d327ec27893c866",
                    ],
                    "index": "pypi",
                    "version": "==2.0.0",
                },
                "python-json-logger": {
                    "hashes": ["sha256:b7a31162f2a01965a5efb94453ce69230ed208468b0bbc7fdfc56e6d8df2e281"],
                    "markers": "python_version >= '2.7'",
                    "version": "==0.1.11",
                },
            },
            "develop": {},
            "sources": [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True}],
        }


def test_parse_poetry2pipfile_lock_only_direct():
    """Test parsing Poetry files and obtaining direct dependencies out of them."""
    work_dir = os.path.join(_DATA_DIR, "parse", "poetry2")
    with cwd(work_dir):
        pipfile_lock = micropipenv._poetry2pipfile_lock(only_direct=True)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)

        assert pipfile_lock == {
            "_meta": {
                "hash": {"sha256": "b5f58798352fe4adc96b3b43d6e509458060cfeb2bc773aaed836a9a9830a2bc"},
                "pipfile-spec": 6,
                "requires": {},
                "sources": [
                    {
                        "name": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                        "url": "https://pypi.org/simple",
                        "verify_ssl": True,
                    }
                ],
            },
            "default": {"daiquiri": "==2.0.0"},
            "develop": {"flexmock": "^0.10.4"},
        }


def test_parse_poetry2pipfile_lock_only_direct_no_default():
    """Test parsing Poetry files and obtaining direct dependencies out of them."""
    work_dir = os.path.join(_DATA_DIR, "parse", "poetry2")
    with cwd(work_dir):
        pipfile_lock = micropipenv._poetry2pipfile_lock(only_direct=True, no_default=True)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)

        assert pipfile_lock == {
            "_meta": {
                "hash": {"sha256": "b5f58798352fe4adc96b3b43d6e509458060cfeb2bc773aaed836a9a9830a2bc"},
                "pipfile-spec": 6,
                "requires": {},
                "sources": [
                    {
                        "name": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                        "url": "https://pypi.org/simple",
                        "verify_ssl": True,
                    }
                ],
            },
            "default": {},
            "develop": {"flexmock": "^0.10.4"},
        }


def test_parse_poetry2pipfile_lock_only_direct_no_dev():
    """Test parsing Poetry files and obtaining direct dependencies out of them."""
    work_dir = os.path.join(_DATA_DIR, "parse", "poetry2")
    with cwd(work_dir):
        pipfile_lock = micropipenv._poetry2pipfile_lock(only_direct=True, no_dev=True)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)

        assert pipfile_lock == {
            "_meta": {
                "hash": {"sha256": "b5f58798352fe4adc96b3b43d6e509458060cfeb2bc773aaed836a9a9830a2bc"},
                "pipfile-spec": 6,
                "requires": {},
                "sources": [
                    {
                        "name": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                        "url": "https://pypi.org/simple",
                        "verify_ssl": True,
                    }
                ],
            },
            "default": {"daiquiri": "==2.0.0"},
            "develop": {},
        }


def test_parse_poetry2pipfile_lock_no_default():
    """Test parsing Poetry files and obtaining only dev dependencies."""
    work_dir = os.path.join(_DATA_DIR, "parse", "poetry2")
    with cwd(work_dir):
        pipfile_lock = micropipenv._poetry2pipfile_lock(no_default=True)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)

        assert pipfile_lock == {
            "_meta": {
                "hash": {"sha256": "b5f58798352fe4adc96b3b43d6e509458060cfeb2bc773aaed836a9a9830a2bc"},
                "pipfile-spec": 6,
                "requires": {},
                "sources": [
                    {
                        "name": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                        "url": "https://pypi.org/simple",
                        "verify_ssl": True,
                    }
                ],
            },
            "default": {},
            "develop": {
                "flexmock": {
                    "hashes": ["sha256:5033ceb974d6452cf8716c2ff5059074b77e546df5c849fb44a53f98dfe0d82c"],
                    "index": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                    "version": "==0.10.4",
                }
            },
        }


def test_parse_poetry2pipfile_lock_no_dev():
    """Test parsing Poetry files and obtaining only default dependencies."""
    work_dir = os.path.join(_DATA_DIR, "parse", "poetry2")
    with cwd(work_dir):
        pipfile_lock = micropipenv._poetry2pipfile_lock(no_dev=True)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)

        assert pipfile_lock == {
            "_meta": {
                "hash": {"sha256": "b5f58798352fe4adc96b3b43d6e509458060cfeb2bc773aaed836a9a9830a2bc"},
                "pipfile-spec": 6,
                "requires": {},
                "sources": [
                    {
                        "name": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                        "url": "https://pypi.org/simple",
                        "verify_ssl": True,
                    }
                ],
            },
            "default": {
                "daiquiri": {
                    "hashes": [
                        "sha256:d57b9fd5432933c6e899054eb62cee22eab89f560c8493254d327ec27893c866",
                        "sha256:6b235ed15b73b87fd3cc2521aacbb727bf8443a0896dc534b07503841d03cfdb",
                    ],
                    "index": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                    "version": "==2.0.0",
                },
                "python-json-logger": {
                    "hashes": ["sha256:b7a31162f2a01965a5efb94453ce69230ed208468b0bbc7fdfc56e6d8df2e281"],
                    "index": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                    "version": "==0.1.11",
                },
            },
            "develop": {},
        }


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
        method="pipenv",
        no_hashes=False,
        no_indexes=False,
        no_versions=False,
        only_direct=True,
        no_default=False,
        no_dev=False,
        no_comments=True,
    ).once()

    micropipenv.main(argv=["requirements", "--only-direct", "--no-comments"])


def test_get_index_entry_str():
    """Test obtaining index configuration for pip when."""
    meta_1 = {
        "hash": {"sha256": "foobar"},
        "pipfile-spec": 6,
        "requires": {},
        "sources": [
            {"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True},
            {"name": "thoth-station", "url": "https://thoth-station.ninja/simple", "verify_ssl": True},
        ],
    }

    assert (
        micropipenv._get_index_entry_str(meta_1)
        == """\
--index-url https://pypi.org/simple
--extra-index-url https://thoth-station.ninja/simple
"""
    )

    meta_2 = {
        "hash": {"sha256": "foobar"},
        "pipfile-spec": 6,
        "requires": {},
        "sources": [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True}],
    }

    assert (
        micropipenv._get_index_entry_str(meta_2)
        == """\
--index-url https://pypi.org/simple
"""
    )

    # System configuration is used.
    assert micropipenv._get_index_entry_str({}) == ""


def test_get_index_entry_str_package_info():
    """Test obtaining index configuration for pip when package information is passed."""
    meta_1 = {
        "hash": {"sha256": "foobar"},
        "pipfile-spec": 6,
        "requires": {},
        "sources": [
            {"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True},
            {"name": "thoth-station", "url": "https://thoth-station.ninja/simple", "verify_ssl": True},
        ],
    }

    assert (
        micropipenv._get_index_entry_str(meta_1, {"index": "thoth-station"})
        == """\
--index-url https://thoth-station.ninja/simple
"""
    )

    with pytest.raises(micropipenv.RequirementsError):
        micropipenv._get_index_entry_str(meta_1, {"index": "unknown"})


@pytest.mark.parametrize(
    "sections",
    [{"sources": [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True}]}, {}, {"sources": []}],
)
def test_iter_index_entry_str(sections):
    """Test iterating over index configuration entries."""
    obj = flexmock()
    # Package info is not relevant in this case.
    flexmock(micropipenv).should_receive("_get_index_entry_str").with_args(sections, package_info={}).and_return(
        obj
    ).once()
    result = micropipenv._iter_index_entry_str(sections, {})
    # An iterator is returned.
    assert next(result) == obj
    with pytest.raises(StopIteration):
        next(result)


@pytest.mark.online
def test_import_toml(venv):
    """Test the correct order of toml modules."""
    # cmd to run the function inside the venv
    cmd = [
        os.path.join(venv.path, "bin", "python3"),
        "-c",
        "from micropipenv import _import_toml; print(_import_toml())",
    ]

    # no toml package should raise an exception
    with pytest.raises(subprocess.CalledProcessError) as exc:
        output = subprocess.check_output(cmd, universal_newlines=True)
        assert "micropipenv.ExtrasMissing" in exc.output

    venv.install("pytoml")
    output = subprocess.check_output(cmd, universal_newlines=True)
    assert "<module 'pytoml'" in output

    # toml, if installed, takes precedence
    venv.install("toml")
    output = subprocess.check_output(cmd, universal_newlines=True)
    assert "<module 'toml'" in output


def test_check_pip_version(venv):
    """Test checking tested pip version.

    Test checking pip compatibility. micropipenv is tested against different
    pip versions and the warning message produced should help users clarify
    which pip versions are supported. If this test fails with newer pip
    releases, adjust the supported pip version requirement in sources.
    """
    assert micropipenv._check_pip_version(raise_on_incompatible=True) is True
