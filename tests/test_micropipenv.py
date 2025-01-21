#!/usr/bin/env python3
# micropipenv
# Copyright(C) 2020 Fridolin Pokorny
# Copyright(C) 2021 Lumir Balhar
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
from flexmock import flexmock
import os
import pytest
import re
import shutil
import subprocess
import json

import micropipenv

from conftest import MICROPIPENV_TEST_PIP_VERSION, PIP_VERSION


_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.relpath(__file__)), "data"))
# Implementation of `toml` to test micropipenv with
# not defined for Python 3.11+ where tomllib is available in stdlib
MICROPIPENV_TEST_TOML_MODULE = os.getenv("MICROPIPENV_TEST_TOML_MODULE")
WIN = sys.platform == "win32"
BIN_DIR = "Scripts" if WIN else "bin"
SP_DIR = ("lib", "site-packages") if WIN else ("lib", "python*", "site-packages")
PY_LE_38 = sys.version_info[:2] <= (3, 8)
MANYLINUX_2014 = PIP_VERSION.major >= 19 and PIP_VERSION.minor >= 3


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
    return os.path.join(venv.path, BIN_DIR, "pip3")


def get_updated_env(venv):
    """Return `os.environ` with added MICROPIPENV_ vars."""
    new_env = dict(os.environ)
    new_env.update({"MICROPIPENV_PIP_BIN": get_pip_path(venv), "MICROPIPENV_DEBUG": "1"})
    return new_env


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


@pytest.mark.parametrize(
    "input,expected",
    [
        [
            "https://pypi.org/simple, https://example.org/simple",
            ("https://pypi.org/simple", "https://example.org/simple"),
        ],
        ["https://example.org/simple", ("https://example.org/simple",)],
        ["", ("https://pypi.org/simple",)],
        [" ", ("https://pypi.org/simple",)],
        ["\t", ("https://pypi.org/simple",)],
        [None, ("https://pypi.org/simple",)],
    ],
)
def test_get_index_urls(input, expected):
    """Test index url parsing"""
    if input is not None:
        os.environ["MICROPIPENV_DEFAULT_INDEX_URLS"] = input
    else:
        del os.environ["MICROPIPENV_DEFAULT_INDEX_URLS"]

    result = micropipenv.get_index_urls()
    assert result == expected


@pytest.mark.online
def test_install_pipenv(venv):
    """Test invoking installation using information in Pipfile.lock."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv")):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"


@pytest.mark.online
def test_install_pipenv_vcs(venv):
    """Test invoking installation using information in Pipfile.lock, a git version is used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_vcs")):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.0.0"


@pytest.mark.online
def test_install_pipenv_vcs_subdir(venv):
    """Test invoking installation using information in Pipfile.lock, a git version and &subdirectory is used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_vcs_subdir")):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("pygstc")) == "0.2.1"


@pytest.mark.online
def test_install_pipenv_file(venv):
    """Test invoking installation using information in Pipfile.lock, a file mode is used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_file")):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"


@pytest.mark.online
def test_install_pipenv_url(venv):
    """Test invoking installation using information in Pipfile.lock, a url source is used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_url")):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "3.0.0"
        assert str(venv.get_version("python-json-logger")) == "2.0.7"


@pytest.mark.online
def test_install_pipenv_editable(venv):
    """Test invoking installation using information in Pipfile.lock, an editable mode is used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_editable")):
        try:
            subprocess.run(cmd, check=True, env=get_updated_env(venv))
            assert str(venv.get_version("daiquiri")) == "2.0.0"
            assert str(venv.get_version("python-json-logger")) == "0.1.11"
            assert str(venv.get_version("micropipenv-editable-test")) == "1.2.3"
            if sys.version_info >= (3, 12):
                assert (
                    len(glob.glob(os.path.join(venv.path, *SP_DIR, "__editable__*micropipenv_editable_test*"))) == 2
                ), "No __editable__ files found for editable install"
            else:
                assert (
                    len(glob.glob(os.path.join(venv.path, *SP_DIR, "micropipenv-editable-test.egg-link"))) == 1
                ), "No egg-link found for editable install"
        finally:
            # Clean up this file, can cause issues across multiple test runs.
            shutil.rmtree("micropipenv_editable_test.egg-info", ignore_errors=True)


# This test does not work on Windows because files in the .git folder
# has some special permissions that the cleanup method of TemporaryDirectory
# from conftest.pytest_configure cannot delete them.
# Python 3.10 has an option to ignore errors like this so we can enable it
# back soon at least for Python 3.10.
# See: https://github.com/python/cpython/pull/24793
@pytest.mark.online
@pytest.mark.skipif(WIN, reason="Fails to remove .git folder on Windows")
def test_install_pipenv_vcs_editable(venv):
    """Test invoking installation using information in Pipfile.lock, a git version in editable mode is used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_vcs_editable")):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "1.6.0"
        if sys.version_info >= (3, 12):
            assert (
                len(glob.glob(os.path.join(venv.path, *SP_DIR, "__editable__*daiquiri*"))) == 2
            ), "No __editable__ files found for editable install"
        else:
            assert (
                len(glob.glob(os.path.join(venv.path, *SP_DIR, "daiquiri.egg-link"))) == 1
            ), "No egg-link found for editable install"


@pytest.mark.online
def test_install_poetry(venv):
    """Test invoking installation using information from a Poetry project."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry")
    with cwd(os.path.join(_DATA_DIR, "install", "poetry")):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
def test_install_poetry_vcs(venv):
    """Test invoking installation using information from a Poetry project, a git version is used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_vcs")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.1.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
def test_install_poetry_vcs_subdir(venv):
    """Test invoking installation using information from a Poetry project, a git version and a subdirectory are used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_vcs_subdir")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("pygstc")) == "0.2.1"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
def test_install_poetry_directory(venv):
    """Test invoking installation using information from a Poetry project, a directory source is used."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_directory")
    with cwd(work_dir):
        if PIP_VERSION is not None and PIP_VERSION.release < (19, 0, 0):
            # Older versions of pip need a setup.py file. Newer versions will remove it if found.
            with open("testproject/setup.py", "w") as setupfile:
                setupfile.write("from setuptools import setup; setup()\n")
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("testproject")) == "0.1.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


# PEP 517 is no longer enough for this test because cffi
# produces manylinux_x_y wheels which are specified in PEP 600
# and supported in pip 20.3+.
# The current complete dependency chain is:
#   cffi>=1.12->cryptography>=2.0->SecretStorage>=3.2->keyring>=21.2.0->poetry>=0.12
@pytest.mark.online
@pytest.mark.skipif(
    PIP_VERSION is not None and PIP_VERSION.release < (20, 3, 0),
    reason="Needs PEP 600 support introduced in pip 20.3",
)
def test_install_poetry_directory_poetry(venv):
    """Test invoking installation using information from a Poetry project, a Poetry project is used as a directory source."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_directory_poetry")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("testproject")) == "0.1.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
def test_install_poetry_complex_example(venv):
    """Test invoking installation using information from a Poetry project. Involves complex dependencies, extras and markers."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_markers_extra")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("requests")) == "2.27.1"
        # Dependency defined as requests[use_chardet_on_py3] extra
        assert venv.get_version("chardet", raises=False) is not None
        # unicodedata2 is provided as charset-normalizer[unicode_backport] but is not specified for installation
        assert venv.get_version("unicodedata2", raises=False) is None
        # also, requests[socks] or urllib3[socks] should not be installed
        assert venv.get_version("PySocks", raises=False) is None


@pytest.mark.online
def test_install_poetry_secondary_source(venv):
    """Test invoking installation using information from a Poetry project with packages from different source indexes."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_secondary_source")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.0.0"  # Installs from standard default PyPI
        assert str(venv.get_version("ada")) == "0.0.0"  # This package is available only on TestPyPI


@pytest.mark.online
def test_install_poetry_lock_format_2(venv):
    """Test invoking installation using information from a Poetry project using lock file format 2."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_lock_format_2")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "2.0.4"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
def test_install_poetry_type_url(venv):
    """Test invoking installation using information from a Poetry project using url source format."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "poetry"]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_url")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "3.0.0"
        assert str(venv.get_version("python-json-logger")) == "2.0.7"

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
@pytest.mark.skipif(PY_LE_38, reason="Deps not compatible with Python <= 3.8")
@pytest.mark.skipif(not MANYLINUX_2014, reason="Deps provided as manylinux2014 wheels - needs pip 19.3+.")
def test_install_poetry_complex_dep_tree_deploy(venv):
    """Test invoking installation using information from a Poetry project using url source format."""
    cmd = [
        os.path.join(venv.path, BIN_DIR, "python"),
        micropipenv.__file__,
        "install",
        "--method",
        "poetry",
        "--deploy",
    ]
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    work_dir = os.path.join(_DATA_DIR, "install", "poetry_complex_dep_tree")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert venv.get_version("h2", raises=False) is not None
        assert venv.get_version("hpack", raises=False) is not None
        assert venv.get_version("hyperframe", raises=False) is not None
        assert venv.get_version("wsproto", raises=False) is not None

        check_generated_pipfile_lock(os.path.join(work_dir, "Pipfile.lock"), os.path.join(work_dir, "_Pipfile.lock"))


@pytest.mark.online
def test_install_pipenv_env_vars(venv):
    """Test installation using enviroment variables in source URL."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_env_vars")):
        subprocess.run(cmd, check=True, env={**get_updated_env(venv), **{"URL": "https://pypi.org/simple"}})
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"


@pytest.mark.online
def test_install_pipenv_env_vars_undefined(venv):
    """Test installation using enviroment variables without setting them."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_env_vars")):
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.check_call(cmd, env=get_updated_env(venv))


@pytest.mark.online
def test_install_pipenv_env_vars_default(venv):
    """Test installation using default values of environment variables."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "pipenv"]
    with cwd(os.path.join(_DATA_DIR, "install", "pipenv_env_vars_default")):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.0.0"
        assert str(venv.get_version("python-json-logger")) == "0.1.11"


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
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("requests")) == "2.22.0"


@pytest.mark.online
def test_install_pip_vcs(venv):
    """Test installation of a package from VCS (git)."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements_vcs")
    with cwd(work_dir):
        subprocess.run(cmd, check=True, env=get_updated_env(venv))
        assert str(venv.get_version("daiquiri")) == "2.1.0"
        assert str(venv.get_version("python-json-logger")) is not None


@pytest.mark.online
def test_install_pip_editable(venv):
    """Test installation of an editable package which is not treated as a lock file."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements_editable_unlocked")
    with cwd(work_dir):
        try:
            subprocess.run(cmd, check=True, env=get_updated_env(venv))
            assert str(venv.get_version("micropipenv-editable-test")) == "3.3.3"
            assert str(venv.get_version("q")) == "1.0"
            if sys.version_info >= (3, 12):
                assert (
                    len(glob.glob(os.path.join(venv.path, *SP_DIR, "__editable__*micropipenv_editable_test*"))) == 2
                ), "No __editable__ files found for editable install"
            else:
                assert (
                    len(glob.glob(os.path.join(venv.path, *SP_DIR, "micropipenv-editable-test.egg-link"))) == 1
                ), "No egg-link found for editable install"
        finally:
            # Clean up this file, can cause issues across multiple test runs.
            shutil.rmtree("micropipenv_editable_test.egg-info", ignore_errors=True)


@pytest.mark.online
def test_install_pip_tools_editable(venv):
    """Test installation of an editable package."""
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "requirements_editable")
    with cwd(work_dir):
        try:
            subprocess.run(cmd, check=True, env=get_updated_env(venv))
            assert str(venv.get_version("micropipenv-editable-test")) == "3.2.1"
            assert str(venv.get_version("daiquiri")) == "2.0.0"
            assert str(venv.get_version("python-json-logger")) == "0.1.11"
            if sys.version_info >= (3, 12):
                assert (
                    len(glob.glob(os.path.join(venv.path, *SP_DIR, "__editable__*micropipenv_editable_test*"))) == 2
                ), "No __editable__ files found for editable install"
            else:
                assert (
                    len(glob.glob(os.path.join(venv.path, *SP_DIR, "micropipenv-editable-test.egg-link"))) == 1
                ), "No egg-link found for editable install"

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
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--method", "requirements"]
    work_dir = os.path.join(_DATA_DIR, "install", "pip-tools_direct_reference")
    with cwd(work_dir):
        with open("requirements.txt", "w") as requirements_file:
            artifact_path = os.path.join(os.getcwd(), "micropipenv-0.0.0.tar.gz")
            requirements_file.write(
                "micropipenv @ file://{} --hash=sha256:03b3f06d0e3c403337c73d8d95b1976449af8985e40a6aabfd9620c282c8d060\n".format(
                    artifact_path
                )
            )

        subprocess.run(cmd, check=True, env=get_updated_env(venv))
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
        assert str(venv.get_version("requests")) == "2.22.0"


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
        assert str(venv.get_version("requests")) == "2.22.0"


@pytest.mark.online
@pytest.mark.parametrize(
    "directory, filename, method",
    [
        ["invalid_pipfile", "Pipfile", "pipenv"],
        ["invalid_poetry_lock", "poetry.lock", "poetry"],
        ["invalid_pyproject_toml", "pyproject.toml", "poetry"],
    ],
)
def test_install_invalid_toml_file(venv, directory, filename, method):
    """Test exception when a Pipfile is not a valid TOML."""
    if MICROPIPENV_TEST_TOML_MODULE:
        venv.install(MICROPIPENV_TEST_TOML_MODULE)
    cmd = [os.path.join(venv.path, BIN_DIR, "python"), micropipenv.__file__, "install", "--deploy", "--method", method]
    work_dir = os.path.join(_DATA_DIR, "install", directory)
    with cwd(work_dir):
        with pytest.raises(subprocess.CalledProcessError) as exception:
            subprocess.check_output(cmd, env=get_updated_env(venv), stderr=subprocess.PIPE, universal_newlines=True)

    assert f"FileReadError: Failed to parse {filename}: " in exception.value.stderr


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


@pytest.mark.parametrize(
    "options, expected_file",
    (
        ({"no_dev": False, "no_default": False}, "Pipfile.lock"),
        ({"no_dev": True, "no_default": False}, "Pipfile_no_dev.lock"),
        ({"no_dev": False, "no_default": True}, "Pipfile_no_default.lock"),
    ),
)
@pytest.mark.parametrize(
    "directory",
    (
        "poetry",
        "poetry_1_5",
        "poetry_default_dev_diff",
        "poetry_default_source_legacy",
        "poetry_legacy_source_and_groups",
        "poetry_lock_format_2",
        "poetry_markers_direct",
        "poetry_markers_extra",
        "poetry_markers_indirect",
        "poetry_markers_order",
        "poetry_markers_skip",
        "poetry_markers_transitive_deps",
        "poetry_normalized_names",
        "poetry_secondary_source",
        "poetry_source_directory",
    ),
)
def test_parse_poetry2pipfile_lock(directory, options, expected_file):
    """Test parsing Poetry specific files into Pipfile.lock representation."""
    work_dir = os.path.join(_DATA_DIR, "parse", directory)
    with cwd(work_dir):
        pipfile_lock = micropipenv._poetry2pipfile_lock(**options)
        with open(expected_file) as f:
            expected_pipfile_lock = json.load(f)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        expected_pipfile_lock["_meta"]["requires"].pop("python_version", None)
        assert pipfile_lock == expected_pipfile_lock
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)


def test_parse_poetry2pipfile_source_without_url():
    """Test parsing Poetry files with source without URL"""
    work_dir = os.path.join(_DATA_DIR, "parse", "poetry_source_without_url")
    with cwd(work_dir):
        pipfile_lock = micropipenv._poetry2pipfile_lock(only_direct=True)

        python_version = pipfile_lock["_meta"]["requires"].pop("python_version")
        assert python_version == "{}.{}".format(sys.version_info.major, sys.version_info.minor)

        assert pipfile_lock == {
            "_meta": {
                "hash": {"sha256": "735029730bde8fac7a13976310edf93d63ef123733a43758632ed3e2879c22ec"},
                "pipfile-spec": 6,
                "requires": {},
                "sources": [
                    {
                        "name": "5a06749b2297be54ac5699f6f2761716adc5001a2d5f8b915ab2172922dd5706",
                        "url": "https://pypi.org/simple",
                        "verify_ssl": True,
                    },
                    {
                        "name": "PyPI",
                        "verify_ssl": True,
                    },
                ],
            },
            "default": {"daiquiri": "==2.0.0"},
            "develop": {"flexmock": "^0.10.4"},
        }


def test_parse_poetry2pipfile_causing_endless_loop():
    """Test parsing Poetry files with source without URL"""
    work_dir = os.path.join(_DATA_DIR, "parse", "poetry_endless_loop")
    with cwd(work_dir):
        with pytest.raises(micropipenv.PoetryError, match="Failed to find package category for: flexmock"):
            micropipenv._poetry2pipfile_lock()


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
        ("poetry_complex", {"no_comments": True}, "requirements_no_comments.txt"),
        ("poetry_complex", {"no_default": True}, "requirements_no_default.txt"),
        ("poetry_complex", {"no_dev": True}, "requirements_no_dev.txt"),
        ("poetry_complex", {"no_hashes": True}, "requirements_no_hashes.txt"),
        ("poetry_complex", {"no_indexes": True}, "requirements_no_indexes.txt"),
        ("poetry_complex", {"no_versions": True}, "requirements_no_versions.txt"),
        ("poetry_complex", {"only_direct": True}, "requirements_only_direct.txt"),
        ("vcs_ref_editable", {"no_comments": True}, "requirements_no_comments.txt"),
        ("vcs_ref_editable", {"no_default": True}, "requirements_no_default.txt"),
        ("vcs_ref_editable", {"no_dev": True}, "requirements_no_dev.txt"),
        ("vcs_ref_editable", {"no_hashes": True}, "requirements_no_hashes.txt"),
        ("vcs_ref_editable", {"no_indexes": True}, "requirements_no_indexes.txt"),
        ("vcs_ref_editable", {"no_versions": True}, "requirements_no_versions.txt"),
        ("vcs_ref_editable", {"only_direct": True}, "requirements_only_direct.txt"),
    ],
)
def test_requirements(tmp_path, test, options, expected_file):
    """Test generating requirements out of Pipfile and Pipfile.lock."""
    source_path = os.path.join(_DATA_DIR, "requirements", test)
    for f in glob.glob(os.path.join(source_path, "*")):
        shutil.copy(f, tmp_path)

    expected_output_file_path = os.path.join(_DATA_DIR, "requirements", test, expected_file)
    with open(expected_output_file_path, "r") as f:
        expected = f.read()

    with cwd(tmp_path):
        with open("output.txt", "w") as f, redirect_stdout(f):
            micropipenv.requirements(**options)
        with open("output.txt", "r") as f:
            assert f.read() == expected


def test_requirements_autodiscovery_not_found(tmp_path):
    """Test raising an exception if auto-discovery is not able to locate requirements files."""
    with cwd(tmp_path):
        with pytest.raises(micropipenv.FileNotFound):
            micropipenv._traverse_up_find_file("Pipfile")

        with pytest.raises(micropipenv.FileNotFound):
            micropipenv._traverse_up_find_file("Pipfile.lock")

        with pytest.raises(micropipenv.FileNotFound):
            micropipenv._traverse_up_find_file("poetry.lock")

        with pytest.raises(micropipenv.FileNotFound):
            micropipenv._traverse_up_find_file("pyproject.toml")

        with pytest.raises(
            micropipenv.FileNotFound,
            match=re.escape(
                f"Failed to find Pipfile.lock or poetry.lock in the current directory or any of its parent: {str(tmp_path)!r}"
            ),
        ):
            micropipenv.requirements()


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
        os.path.join(venv.path, BIN_DIR, "python"),
        "-c",
        "from micropipenv import _import_toml; print(_import_toml())",
    ]

    # Python 3.11 has tomllib in stdlib and it has the highest priority
    # no matter what is or isn't installed in the virtual environment.
    if sys.version_info >= (3, 11):
        output = subprocess.check_output(cmd, universal_newlines=True)
        assert "<module 'tomllib'" in output
        return

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


@pytest.mark.skipif(
    not MICROPIPENV_TEST_PIP_VERSION or MICROPIPENV_TEST_PIP_VERSION == "git", reason="Unsuitable pip version"
)
@pytest.mark.parametrize("raise_on_incompatible", (True, False))
def test_check_pip_version_compatible(raise_on_incompatible):
    """Test checking tested pip version.

    Test checking pip compatibility. micropipenv is tested against different
    pip versions and the warning message produced should help users clarify
    which pip versions are supported.

    This test runs for stable releases of pip and the function
    should always return True.
    """
    micropipenv.pip_version = str(PIP_VERSION)
    assert micropipenv._check_pip_version(raise_on_incompatible=raise_on_incompatible) is True


@pytest.mark.skipif(
    not MICROPIPENV_TEST_PIP_VERSION or MICROPIPENV_TEST_PIP_VERSION != "git", reason="Unsuitable pip version"
)
@pytest.mark.parametrize("raise_on_incompatible", (True, False))
def test_check_pip_version_incompatible(raise_on_incompatible):
    """Test checking tested pip version.

    Test checking pip compatibility. micropipenv is tested against different
    pip versions and the warning message produced should help users clarify
    which pip versions are supported.

    This test runs for pip versions like "21.2.dev0" and the function
    should therefore report the incompatibility.
    """
    micropipenv.pip_version = str(PIP_VERSION)
    if raise_on_incompatible:
        with pytest.raises(micropipenv.CompatibilityError):
            micropipenv._check_pip_version(raise_on_incompatible=raise_on_incompatible)
    else:
        assert micropipenv._check_pip_version(raise_on_incompatible=raise_on_incompatible) is False


@pytest.mark.parametrize(
    ("name", "expected"),
    (
        ("importlib_metadata", "importlib-metadata"),
        ("Django", "django"),
        ("jaraco.packaging", "jaraco-packaging"),
        ("foo_bar.baz", "foo-bar-baz"),
        ("foo---bar", "foo-bar"),
        ("foo___bar...baz", "foo-bar-baz"),
    ),
)
def test_normalize_package_name(name, expected):
    """Test package name normalization."""
    assert micropipenv.normalize_package_name(name) == expected


@pytest.mark.parametrize(
    ("info", "expected"),
    (
        ({"path": "."}, "."),
        ({"path": "file:///path/to/package"}, "file:///path/to/package"),
        ({"path": "/path/to/package"}, "/path/to/package"),
        ({"path": "./path/to/package"}, "./path/to/package"),
        ({"path": "package"}, "./package"),
    ),
)
def test_get_package_entry_str(info, expected):
    """Test possible formats of the "path" option."""
    result = micropipenv._get_package_entry_str("testpackage", info).strip()
    assert result == expected


@pytest.mark.parametrize("path", ["poetry", "poetry_group", "poetry_2_project"])
def test_poetry_lockfile_verify(path):
    """Test verifying poetry lockfile."""
    with cwd(os.path.join(_DATA_DIR, "verify", path)):
        micropipenv.verify_poetry_lockfile()


def test_poetry_lockfile_verify_error_hash():
    """Test verifying poetry lockfile with an out-of-date content hash."""
    with cwd(os.path.join(_DATA_DIR, "verify", "poetry_error_hash")):
        err_msg = (
            "Poetry.lock hash 'foobar' does not correspond to hash computed based "
            "on pyproject.toml '46444b08fe9dc1a5b346aa11e455aaa41feffd77a377d86037fe55cffb0ec682', "
            "aborting deployment"
        )
        with pytest.raises(micropipenv.HashMismatch, match=err_msg):
            micropipenv.verify_poetry_lockfile()


def test_pipenv_lockfile_verify(venv):
    """Test verifying Pipenv lockfile."""
    with cwd(os.path.join(_DATA_DIR, "verify", "pipenv")):
        micropipenv.verify_pipenv_lockfile()


def test_pipenv_lockfile_verify_error_hash(venv):
    """Test verifying pipenv lockfile with an out-of-date content hash."""
    with cwd(os.path.join(_DATA_DIR, "verify", "pipenv_error_hash")):
        err_msg = (
            "Pipfile.lock hash 'foobar' does not correspond to hash computed based "
            "on Pipfile '8b8dfe383cda8e22d95623518c911b7d5cf28acb8fccd4b7d8dc67fce444b6d3', "
            "aborting deployment"
        )
        with pytest.raises(micropipenv.HashMismatch, match=err_msg):
            micropipenv.verify_pipenv_lockfile()


def test_pipenv_lockfile_verify_error_python():
    """Test verifying pipenv lockfile with a mismatched python version."""
    with cwd(os.path.join(_DATA_DIR, "verify", "pipenv_error_python")):
        err_msg = r"Running Python version \d+.\d+, but Pipfile.lock requires Python version 5.9"
        with pytest.raises(micropipenv.PythonVersionMismatch, match=err_msg):
            micropipenv.verify_pipenv_lockfile()
