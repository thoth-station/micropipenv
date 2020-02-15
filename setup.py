from setuptools.command.test import test as TestCommand
from setuptools import setup
import os
import sys


def get_version():
    """Get version of micropipenv.py."""
    with open(os.path.join("micropipenv.py")) as f:
        content = f.readlines()

    for line in content:
        if line.startswith("__version__ ="):
            # dirty, remove trailing and leading chars
            return line.split(" = ")[1][1:-2]

    raise ValueError("No version identifier found")


class Test(TestCommand):
    """Introduce test command to run testsuite using pytest."""

    _IMPLICIT_PYTEST_ARGS = [
        "--timeout=5",
        "--mypy",
        "micropipenv.py",
        "--capture=no",
        "--verbose",
        "-l",
        "-s",
        "-vv",
        "tests/",
    ]

    user_options = [("pytest-args=", "a", "Arguments to pass into py.test")]

    def initialize_options(self):
        super().initialize_options()
        self.pytest_args = None

    def finalize_options(self):
        super().finalize_options()
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest

        passed_args = list(self._IMPLICIT_PYTEST_ARGS)

        if self.pytest_args:
            self.pytest_args = [arg for arg in self.pytest_args.split() if arg]
            passed_args.extend(self.pytest_args)

        sys.exit(pytest.main(passed_args))


setup(
    name="micropipenv",
    version=get_version(),
    description="A simple wrapper around pip to support Pipenv files",
    url="https://github.com/thoth-station/micropipenv",
    download_url="https://pypi.org/project/micropipenv",
    long_description=open(os.path.join(os.path.dirname(__file__), "README.rst")).read(),
    author="Fridolin Pokorny",
    author_email="fridex.devel@gmail.com",
    license="GPLv3+",
    py_modules=["micropipenv"],
    cmdclass={"test": Test},
    entry_points={"console_scripts": ["micropipenv=micropipenv:main"]},
    extras_require={
        "toml": ["toml"],
    },
)
