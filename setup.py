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

setup(
    name="micropipenv",
    version=get_version(),
    description="A simple wrapper around pip to support requirements.txt, Pipenv and Poetry files for containerized applications",
    url="https://github.com/thoth-station/micropipenv",
    download_url="https://pypi.org/project/micropipenv",
    long_description=open(os.path.join(os.path.dirname(__file__), "README.rst")).read(),
    author="Fridolin Pokorny",
    author_email="fridex.devel@gmail.com",
    license="GPLv3+",
    py_modules=["micropipenv"],
    install_requires=["pip>=9"],
    entry_points={"console_scripts": ["micropipenv=micropipenv:main"]},
    extras_require={
        "toml": ["toml"],
    },
)
