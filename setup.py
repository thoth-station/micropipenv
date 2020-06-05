from setuptools.command.test import test as TestCommand
from setuptools import setup
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))



def get_version():
    """Get version of micropipenv.py."""
    with open(os.path.join(_HERE, "micropipenv.py")) as f:
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
    keywords=["packaging", "pipenv", "poetry", "pip", "dependencies", "dependency-management", "utilities"],
    url="https://github.com/thoth-station/micropipenv",
    download_url="https://pypi.org/project/micropipenv",
    long_description=open(os.path.join(_HERE, "README.rst")).read(),
    long_description_content_type="text/x-rst",
    author="Fridolin Pokorny",
    author_email="fridex.devel@gmail.com",
    maintainer="Fridolin Pokorny",
    maintainer_email="fridex.devel@gmail.com",
    license="LGPLv3+",
    py_modules=["micropipenv"],
    install_requires=["pip>=9"],
    entry_points={"console_scripts": ["micropipenv=micropipenv:main"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    extras_require={
        "toml": ["toml"],
    },
)
