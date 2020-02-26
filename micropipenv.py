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

"""A lightweight wrapper for pip to support Pipenv files.

This wrapper can convert Pipfile/Pipfile.lock to requirements.in and/or
requirements.txt file suitable for setup.py script or for pip-tools.

Moreover, this wrapper can mimic `pipenv install --deploy`. For any resolved
stack, micropipenv can parse Pipfile/Pipfile.lock and install required
dependencies using raw pip. The virtual environment is not created, but one can
issue `python3 -m venv venv/ && . venv/bin/activate` to create one.
"""

__version__ = "0.0.4"
__author__ = "Fridolin Pokorny <fridex.devel@gmail.com>"
__title__ = "micropipenv"
__all__ = [
    "ArgumentsError",
    "ExtrasMissing",
    "FileNotFound",
    "FileReadError",
    "get_requirements_sections",
    "HashMismatch",
    "install",
    "main",
    "MicropipenvException",
    "PythonVersionMismatch",
    "requirements",
]

import argparse
import logging
import sys
import json
import os
import hashlib
import subprocess
import tempfile
from collections import deque
from itertools import chain
from urllib.parse import urlparse

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

if TYPE_CHECKING:
    from typing import Any
    from typing import Dict
    from typing import List
    from typing import Optional
    from typing import Union


_LOGGER = logging.getLogger(__title__)
_MAX_DIR_TRAVERSAL = 42  # Avoid any symlinks that would loop.
_PIP_BIN = os.getenv("MICROPIPENV_PIP_BIN", "pip")
_DEBUG = int(os.getenv("MICROPIPENV_DEBUG", 0))


class MicropipenvException(Exception):
    """A base class for all micropipenv exceptions."""


class FileNotFound(MicropipenvException):
    """Raised if the given file was not found on the filesystem."""


class FileReadError(MicropipenvException):
    """Raised if the given file cannot be loaded or parsed."""


class ExtrasMissing(MicropipenvException):
    """Raised when micropipenv was invoked with functionality requiring a missing extras."""


class ArgumentsError(MicropipenvException):
    """Raised when arguments passed are disjoint or wrong."""


class PythonVersionMismatch(MicropipenvException):
    """Raised if Python version found does not correspond to the one present in Pipfile.lock."""


class HashMismatch(MicropipenvException):
    """Raised when computed hash out of Pipfile does not correspond to the hash stated in Pipfile.lock."""


class PipInstallError(MicropipenvException):
    """Raised when `pip install` returned a non-zero exit code."""


def _traverse_up_find_file(file_name):  # type: (str) -> str
    """Traverse the root up, find the given file by name and return its path."""
    path = os.getcwd()
    traversed = _MAX_DIR_TRAVERSAL
    while traversed > 0:
        if file_name in os.listdir(path):
            _LOGGER.debug("Found %r in %r", file_name, path)
            return os.path.join(path, file_name)

        traversed -= 1
        path = os.path.realpath(os.path.join(path, ".."))
    else:
        raise FileNotFound("File {!r} not found in {!r} or any parent directory".format(file_name, os.getcwd()))


def _read_pipfile_lock():  # type: () -> Any
    """Find and load Pipfile.lock"""
    pipfile_lock_path = _traverse_up_find_file("Pipfile.lock")
    try:
        with open(pipfile_lock_path) as input_file:
            content = json.load(input_file)
    except json.JSONDecodeError as exc:
        raise FileReadError("Filed to parse Pipfile.lock: {}".format(str(exc))) from exc
    except Exception as exc:
        raise FileReadError(str(exc)) from exc

    pipfile_spec_version = content.get("_meta", {}).get("pipfile-spec")
    if pipfile_spec_version != 6:
        _LOGGER.warning("Unsupported Pipfile.lock spec version - supported is 6, got {}".format(pipfile_spec_version))

    return content


def _read_pipfile():  # type: () -> Any
    """Find and read Pipfile."""
    try:
        import toml
    except ImportError as exc:
        raise ExtrasMissing(
            "Failed to import toml needed for parsing Pipfile, please install micropipenv "
            "with toml extra: pip install micropipenv[toml]"
        ) from exc

    pipfile_path = _traverse_up_find_file("Pipfile")

    try:
        with open(pipfile_path) as input_file:
            return toml.load(input_file)
    except toml.TomlDecodeError as exc:
        raise FileReadError("Failed to parse Pipfile: {}".format(str(exc))) from exc
    except Exception as exc:
        raise FileReadError(str(exc)) from exc


def _compute_pipfile_hash(pipfile):  # type: (Dict[str, Any]) -> str
    """Compute Pipfile hash based on its content."""
    data = {
        "_meta": {"requires": pipfile.get("requires", {}), "sources": pipfile["source"]},
        "default": pipfile.get("packages", {}),
        "develop": pipfile.get("dev-packages", {}),
    }
    content = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf8")).hexdigest()


def install(
    pipfile=None, pipfile_lock=None, *, deploy=False, dev=False, pip_args=None
):  # type: (Optional[Dict[str, Any]], Optional[Dict[str, Any]], bool, bool, Optional[List[str]]) -> None
    """Perform installation of packages from Pipfile.lock."""
    pipfile_lock = pipfile_lock or _read_pipfile_lock()

    sections = get_requirements_sections(pipfile_lock=pipfile_lock, no_dev=not dev)
    if deploy:
        python_version = pipfile_lock["_meta"].get("requires", {}).get("python_version")
        if python_version is not None:
            if python_version != "{}.{}".format(sys.version_info.major, sys.version_info.minor):
                raise PythonVersionMismatch(
                    "Running Python version {}.{}, but Pipfile.lock requires "
                    "Python version {}".format(sys.version_info.major, sys.version_info.minor, python_version)
                )
        else:
            _LOGGER.warning("No Python version requirement in Pipfile.lock found, no Python version check is performed")

        pipfile_lock_hash = pipfile_lock.get("_meta", {}).get("hash", {}).get("sha256")
        pipfile_hash = _compute_pipfile_hash(pipfile or _read_pipfile())
        if pipfile_hash != pipfile_lock_hash:
            raise HashMismatch(
                "Pipfile.lock hash {!r} does not correspond to hash computed based on "
                "Pipfile {!r}, aborting deployment".format(pipfile_lock_hash, pipfile_hash)
            )

    index_config_str = _get_index_entry_str(sections)

    tmp_file = tempfile.NamedTemporaryFile("w", prefix="requirements.txt", delete=False)
    _LOGGER.debug("Using temporary file for storing requirements: %r", tmp_file.name)

    cmd = [_PIP_BIN, "install", "--no-deps", "-r", tmp_file.name, *(pip_args or [])]
    _LOGGER.debug("Requirements will be installed using %r", cmd)

    packages = chain(
        sections.get("default", {}).items(),
        sections.get("develop", {}).items() if dev else []
    )

    # We maintain an integer assigned to each package - this integer holds a value - how
    # many times the given package failed to install. If a package fails to install, it is
    # re-scheduled to the next installation round, until we try all the packages to
    # satisfy requirements. If any package succeeds with installation, the integer is
    # set to 0 again for all failed installations. This way we can break "cycles" in
    # installation errors.
    to_install = deque({"package_name": i[0], "info": i[1], "error": 0} for i in packages)
    try:
        while to_install:
            entry = to_install.popleft()
            package_name, info, had_error = entry["package_name"], entry["info"], entry["error"]

            with open(tmp_file.name, "w") as f:
                f.write(index_config_str)
                f.write(_get_package_entry_str(package_name, info))

            _LOGGER.debug("Installing %r", package_name)
            called_process = subprocess.run(cmd)

            if called_process.returncode != 0:
                if len(to_install) == 0 or (had_error and had_error > len(to_install)):
                    raise PipInstallError(
                        "Failed to install requirements, dependency {!r} could not be installed".format(package_name)
                    )

                _LOGGER.warning("Failed to install %r, will try in next installation round...", package_name)
                to_install.append({"package_name": package_name, "info": info, "error": had_error + 1})
            else:
                # Discard any error flag if we have any packages that fail to install.
                for item in reversed(to_install):
                    if item["error"] == 0:
                        # Fast path - errors are always added to the end of the queue,
                        # if we find a package without any error we can safely break.
                        break
                    item["error"] = 0
    finally:
        os.remove(tmp_file.name)


def _parse_pipfile_dependency_info(pipfile_entry):  # type: (Union[str, Dict[str, Any]]) -> Dict[str, Any]
    """Parse a Pipfile entry for a package and return a compatible version with Pipfile.lock entry."""
    if isinstance(pipfile_entry, str):
        return {"version": pipfile_entry}
    elif isinstance(pipfile_entry, dict):
        result = {"version": pipfile_entry["version"]}

        if pipfile_entry.get("extras"):
            result["extras"] = pipfile_entry["extras"]

        if pipfile_entry.get("markers"):
            result["markers"] = pipfile_entry["markers"]

        return result

    raise ValueError("Unknown entry in Pipfile (should be of type dict or a str): {}".format(pipfile_entry))


def get_requirements_sections(
    *, pipfile=None, pipfile_lock=None, no_indexes=False, only_direct=False, no_default=False, no_dev=False
):  # type: (Optional[Dict[str, Any]], Optional[Dict[str, Any]], bool, bool, bool, bool) -> Dict[str, Dict[str, Any]]
    """Compute requirements of an application, the output generated is compatible with pip-tools."""
    if no_dev and no_default:
        raise ArgumentsError("Cannot produce requirements as both, default and dev were asked to be discarded")

    result = {}

    if only_direct:
        pipfile = pipfile or _read_pipfile()

        if not no_indexes:
            result["sources"] = pipfile.get("source", [])

        if not no_default:
            result["default"] = {
                dependency_name: _parse_pipfile_dependency_info(pipfile_entry)
                for dependency_name, pipfile_entry in pipfile.get("packages", {}).items()
            }

        if not no_dev:
            result["develop"] = {
                dependency_name: _parse_pipfile_dependency_info(pipfile_entry)
                for dependency_name, pipfile_entry in pipfile.get("dev-packages", {}).items()
            }

        return result

    pipfile_lock = pipfile_lock or _read_pipfile_lock()

    if not no_indexes:
        result["sources"] = pipfile_lock.get("_meta", {}).get("sources", [])

    if not no_default:
        result["default"] = pipfile_lock.get("default", {})

    if not no_dev:
        result["develop"] = pipfile_lock.get("develop", {})

    return result


def _get_package_entry_str(
    package_name, info, *, no_hashes=False, no_versions=False
):  # type: (str, Dict[str, Any], bool, bool) -> str
    """Print entry for the given package."""
    result = package_name

    if info.get("extras"):
        result += "[{}]".format(",".join(info["extras"]))

    if not no_versions and info.get("version") and info["version"] != "*":
        result += info["version"]

    if info.get("markers"):
        result += "; {}".format(info["markers"])

    if not (no_hashes or no_versions):
        for digest in info.get("hashes", []):
            result += " \\\n"
            result += "    --hash={}".format(digest)

    return result + "\n"


def _get_index_entry_str(sections):  # type: (Dict[str, Any]) -> str
    """Get configuration entry for Python package indexes."""
    result = ""
    for idx, source in enumerate(sections.get("sources", [])):
        if idx == 0:
            result += "--index-url {}\n".format(source["url"])
        else:
            result += "--extra-index-url {}\n".format(source["url"])

        if not source["verify_ssl"]:
            result += "--trusted-host {}\n".format(urlparse(source["url"]).netloc)

    return result


def requirements_str(
    sections=None,
    *,
    no_hashes=False,
    no_indexes=False,
    no_versions=False,
    only_direct=False,
    no_default=False,
    no_dev=False,
    no_comments=False,
):  # type: (Optional[Dict[str, Any]], bool, bool, bool, bool, bool, bool, bool) -> str
    """Show requirements of an application, the output generated is compatible with pip-tools."""
    sections = sections or get_requirements_sections(
        no_indexes=no_indexes, only_direct=only_direct, no_default=no_default, no_dev=no_dev
    )

    result = _get_index_entry_str(sections)

    if not no_comments and sections.get("default"):
        result += "#\n# Default dependencies\n#\n"

    for package_name, info in sections.get("default", {}).items():
        result += _get_package_entry_str(package_name, info, no_versions=no_versions, no_hashes=no_hashes)

    if not no_comments and sections.get("develop"):
        result += "#\n# Dev dependencies\n#\n"

    for package_name, info in sections.get("develop", {}).items():
        result += _get_package_entry_str(package_name, info, no_versions=no_versions, no_hashes=no_hashes)

    return result


def requirements(
    sections=None,
    *,
    no_hashes=False,
    no_indexes=False,
    no_versions=False,
    only_direct=False,
    no_default=False,
    no_dev=False,
    no_comments=False,
):  # type: (Optional[Dict[str, Any]], bool, bool, bool, bool, bool, bool, bool) -> None
    """Show requirements of an application, the output generated is compatible with pip-tools."""
    sections = sections or get_requirements_sections(
        no_indexes=no_indexes, only_direct=only_direct, no_default=no_default, no_dev=no_dev
    )
    print(
        requirements_str(
            sections,
            no_hashes=no_hashes,
            no_indexes=no_indexes,
            no_versions=no_versions,
            only_direct=only_direct,
            no_default=no_default,
            no_dev=no_dev,
            no_comments=no_comments,
        ),
        end="",
    )


def main(argv=None):  # type: (Optional[List[str]]) -> int
    """Main for micropipenv."""
    argv = argv or sys.argv[1:]

    parser = argparse.ArgumentParser(prog=__title__, description=__doc__)
    parser.add_argument("--version", help="Print version information and exit.", action="version", version=__version__)
    parser.add_argument("--verbose", action="count", help="Increase verbosity, can be supplied multiple times.")

    subparsers = parser.add_subparsers()

    parser_install = subparsers.add_parser("install", help=install.__doc__)
    parser_install.add_argument(
        "--deploy",
        help="Abort if the Pipfile.lock is out-of-date, or Python version "
        "is wrong; this requires 'toml' extras to be installed.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_DEPLOY", 0))),
    )
    parser_install.add_argument(
        "--dev",
        help="Install both develop and default packages.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_DEV", os.getenv("PIPENV_DEV", 0)))),
    )
    parser_install.add_argument(
        "pip_args",
        help="Specify additional argument to pip, can be supplied multiple times (add "
             "'--' to command line to delimit positional arguments that start with dash "
             "from CLI options).",
        nargs="*",
    )
    parser_install.set_defaults(func=install)

    parser_requirements = subparsers.add_parser("requirements", aliases=["req"], help=requirements.__doc__)
    parser_requirements.add_argument(
        "--no-hashes",
        help="Do not include hashes in the generated output.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_NO_HASHES", 0))),
    )
    parser_requirements.add_argument(
        "--no-indexes",
        help="Do not include index configuration in the generated output.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_NO_INDEXES", 0))),
    )
    parser_requirements.add_argument(
        "--no-versions",
        help="Do not include version information in the generated output, implies --no-hashes.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_NO_VERSIONS", 0))),
    )
    parser_requirements.add_argument(
        "--only-direct",
        help="Include only direct dependencies in the output, implies --no-hashes "
        "and --no-versions; this requires 'toml' extras to be installed.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_ONLY_DIRECT", 0))),
    )
    parser_requirements.add_argument(
        "--no-comments",
        help="Do not include comments differentiating sections.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_NO_COMMENTS", 0))),
    )
    parser_requirements.add_argument(
        "--no-default",
        help="Include only development dependencies, do not include default dependencies.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_NO_DEFAULT", 0))),
    )
    parser_requirements.add_argument(
        "--no-dev",
        help="Include only default dependencies, do not include develop dependencies.",
        action="store_true",
        required=False,
        default=bool(int(os.getenv("MICROPIPENV_NO_DEV", 0))),
    )
    parser_requirements.set_defaults(func=requirements)

    arguments = vars(parser.parse_args(argv))
    handler = arguments.pop("func", None)

    if not handler:
        parser.print_help()
        return 1

    verbose = arguments.pop("verbose", 0)
    if (verbose is not None and verbose >= 2) or _DEBUG:
        _LOGGER.setLevel(logging.DEBUG)
        _LOGGER.debug("Debug mode is on.")
        _LOGGER.debug("Running %r with arguments %r", handler.__name__, arguments)
    elif verbose == 1:
        _LOGGER.setLevel(logging.INFO)
    else:
        _LOGGER.setLevel(logging.WARNING)

    try:
        handler(**arguments)
    except Exception as exc:
        if _LOGGER.level <= logging.DEBUG:
            raise

        _LOGGER.error(str(exc))
        return 3

    return 0


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s %(name)-12s %(levelname)-6s %(message)s", datefmt="%m-%d-%y %H:%M:%S")
    sys.exit(main())
