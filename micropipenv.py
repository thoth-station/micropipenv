#!/usr/bin/env python3
# micropipenv
# Copyright(C) 2020 Fridolin Pokorny
# Copyright(C) 2021 Lumir Balhar
#
# This program is free software: you can redistribute it and / or modify it
# under the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""A lightweight wrapper for pip to support Pipenv/Poetry/requriements files.

This wrapper can convert Pipfile/Pipfile.lock/poetry.lock to requirements.in
and/or requirements.txt file suitable for setup.py script or for pip-tools.

Moreover, this wrapper can mimic `pipenv install --deploy` or `poetry install`.
For any resolved stack, micropipenv can parse
Pipfile/Pipfile.lock/poetry.lock/requirements.txt and install required
dependencies using raw pip. The virtual environment is not created, but one can
issue `python3 -m venv venv/ && . venv/bin/activate` to create one.
"""

__version__ = "1.9.0"
__author__ = "Fridolin Pokorny <fridex.devel@gmail.com>"
__title__ = "micropipenv"

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict, deque, OrderedDict
from itertools import chain
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__title__)
_SUPPORTED_PIP_STR = ">=9,<=25.0.1"  # Respects requirement in setup.py and latest pip to release date.

try:
    from pip import __version__ as pip_version
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.version import Version
    from pip._vendor.packaging.specifiers import SpecifierSet

    try:
        from pip._internal.req import parse_requirements
    except ImportError:  # for pip<10
        from pip.req import parse_requirements  # type: ignore

    try:
        try:
            from pip._internal.network.session import PipSession
        except ImportError:
            from pip._internal.download import PipSession  # type: ignore
    except ImportError:
        from pip.download import PipSession  # type: ignore
    try:
        from pip._internal.index.package_finder import PackageFinder
    except ImportError:
        try:
            from pip._internal.index import PackageFinder  # type: ignore
        except ImportError:
            from pip.index import PackageFinder  # type: ignore
except Exception:
    _LOGGER.error("Check your pip version, supported pip versions: %s", _SUPPORTED_PIP_STR)
    raise

if TYPE_CHECKING:
    from typing import Any
    from typing import Dict
    from typing import Generator
    from typing import List
    from typing import MutableMapping
    from typing import Optional
    from typing import Sequence
    from typing import Tuple
    from typing import Union
    from pip._internal.req.req_file import ParsedRequirement


def get_index_urls():  # type: () -> Tuple[str, ...]
    """Return parsed MICROPIPENV_DEFAULT_INDEX_URLS env variable or the default value."""
    urls = os.getenv("MICROPIPENV_DEFAULT_INDEX_URLS")
    if urls and urls.strip() != "":
        return tuple([url.strip() for url in urls.split(",")])
    return ("https://pypi.org/simple",)


_DEFAULT_INDEX_URLS = get_index_urls()
_MAX_DIR_TRAVERSAL = 42  # Avoid any symlinks that would loop.
_PIP_BIN = os.getenv("MICROPIPENV_PIP_BIN", "pip")
_SUPPORTED_PIP = SpecifierSet(_SUPPORTED_PIP_STR)
_DEBUG = int(os.getenv("MICROPIPENV_DEBUG", 0))
_NO_LOCKFILE_PRINT = int(os.getenv("MICROPIPENV_NO_LOCKFILE_PRINT", 0))
_NO_LOCKFILE_WRITE = int(os.getenv("MICROPIPENV_NO_LOCKFILE_WRITE", 0))
_FILE_METHOD_MAP = OrderedDict(
    [  # The order here defines priorities
        ("Pipfile.lock", "pipenv"),
        ("poetry.lock", "poetry"),
        ("requirements.txt", "requirements"),
    ]
)
__re_nested_vars = re.compile(r"\$\{(?P<name>[^\}:]*)(?::-(?P<default>[^\}]*))?\}")
__re_sub_vars = re.compile(r"\$\{[^}]*\}")


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


class PipRequirementsNotLocked(MicropipenvException):
    """Raised when requirements in requirements.txt are not fully locked."""


class RequirementsError(MicropipenvException):
    """Raised when requirements file has any issue."""


class PoetryError(MicropipenvException):
    """Raised when any of the pyproject.toml or poetry.lock file has any issue."""


class CompatibilityError(MicropipenvException):
    """Raised when internal pip API is incompatible with micropipenv."""


class NotSupportedError(MicropipenvException):
    """Raised when the given feature is not supported by micropipenv."""


def normalize_package_name(package_name):  # type: (str) -> str
    """Implement package name normalization as decribed in PEP 503."""
    return re.sub(r"[-_.]+", "-", package_name).lower()


def _check_pip_version(raise_on_incompatible=False):  # type: (bool) -> bool
    """Check pip version running."""
    if Version(pip_version) not in _SUPPORTED_PIP:
        msg = "pip in version {!r} not tested, tested versions: {!r}".format(pip_version, _SUPPORTED_PIP_STR)
        if raise_on_incompatible:
            raise CompatibilityError(msg)
        _LOGGER.warning(msg)
        return False

    return True


def _import_toml():  # type: () -> Any
    """Import and return tomllib, toml, pytoml, or tomli module (in this order)."""
    exception_names = {
        "tomllib": "TOMLDecodeError",
        "toml": "TomlDecodeError",
        "pytoml": "TomlError",
        "tomli": "TOMLDecodeError",
    }

    # Only tomli/tomllib requires TOML files to be opened
    # in binary mode: https://github.com/hukkin/tomli#parse-a-toml-file
    open_kwargs = defaultdict(dict)  # type: Dict[str, Dict[str, str]]
    open_kwargs["tomli"] = open_kwargs["tomllib"] = {"mode": "rb"}

    for module_name in "tomllib", "toml", "pytoml", "tomli":
        try:
            module = import_module(module_name)
            exception = getattr(module, exception_names[module_name])
            return module, exception, open_kwargs[module_name]
        except ImportError:
            pass
    else:
        raise ExtrasMissing(
            "Failed to import toml needed for parsing Pipfile, please install micropipenv "
            "with toml extra: pip install micropipenv[toml]"
        )


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
    """Find and load Pipfile.lock."""
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
    toml, toml_exception, open_kwargs = _import_toml()

    pipfile_path = _traverse_up_find_file("Pipfile")

    try:
        with open(pipfile_path, **open_kwargs) as input_file:
            return toml.load(input_file)
    except toml_exception as exc:
        raise FileReadError("Failed to parse Pipfile: {}".format(str(exc))) from exc
    except Exception as exc:
        raise FileReadError(str(exc)) from exc


def _read_poetry():  # type: () -> Tuple[MutableMapping[str, Any], MutableMapping[str, Any]]
    """Find and read poetry.lock and pyproject.toml."""
    toml, toml_exception, open_kwargs = _import_toml()

    poetry_lock_path = _traverse_up_find_file("poetry.lock")
    pyproject_toml_path = _traverse_up_find_file("pyproject.toml")

    try:
        with open(poetry_lock_path, **open_kwargs) as input_file:
            poetry_lock = toml.load(input_file)
    except toml_exception as exc:
        raise FileReadError("Failed to parse poetry.lock: {}".format(str(exc))) from exc
    except Exception as exc:
        raise FileReadError(str(exc)) from exc

    try:
        with open(pyproject_toml_path, **open_kwargs) as input_file:
            pyproject_toml = toml.load(input_file)
    except toml_exception as exc:
        raise FileReadError("Failed to parse pyproject.toml: {}".format(str(exc))) from exc
    except Exception as exc:
        raise FileReadError(str(exc)) from exc

    return poetry_lock, pyproject_toml


def _compute_pipfile_hash(pipfile):  # type: (Dict[str, Any]) -> str
    """Compute Pipfile hash based on its content."""
    data = {
        "_meta": {"requires": pipfile.get("requires", {}), "sources": pipfile["source"]},
        "default": pipfile.get("packages", {}),
        "develop": pipfile.get("dev-packages", {}),
    }
    content = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf8")).hexdigest()


def _compute_poetry_hash(pyproject):  # type: (MutableMapping[str, Any]) -> str
    """Compute pyproject.toml hash based on poetry content."""
    project_data = pyproject.get("project", {})
    poetry_data = pyproject.get("tool", {}).get("poetry", {})

    # legacy_keys are the original (pre poetry 2) concept, and should be in
    # the relevant_content even if their value is None as long as it is not a poetry 2 config.
    legacy_keys = ["dependencies", "source", "extras", "dev-dependencies"]
    # group is a new key since poetry 1.2, and must be included
    # if pyproject.toml contains it. Including it always would break
    # backward compatibility.
    # See: https://github.com/python-poetry/poetry/blob/4a07b5e0243bb8879dd6725cb901d9fa0f6eb182/src/poetry/packages/locker.py#L278-L293
    relevant_keys = [*legacy_keys, "group"]
    relevant_project_keys = ["requires-python", "dependencies", "optional-dependencies"]

    relevant_project_content = {k: project_data[k] for k in relevant_project_keys if project_data.get(k)}
    relevant_poetry_content = {}
    for key in relevant_keys:
        value = poetry_data.get(key)
        # Set legacy keys as None for backwards compatibility to older poetry configs
        if not value and (key not in legacy_keys or relevant_project_content):
            continue
        relevant_poetry_content[key] = value

    relevant_content = relevant_poetry_content
    if relevant_project_content:
        # project is introduced as the new format in poetry 2.0 and must be used when configured.
        # Always using the new format would break backward compatibility.
        # See: https://github.com/python-poetry/poetry/blob/6f6fd7012983a2e749c6030c1f5f155fd4397058/src/poetry/packages/locker.py#L266-L302
        relevant_content = {
            "project": relevant_project_content,
            "tool": {"poetry": relevant_content},
        }

    return hashlib.sha256(json.dumps(relevant_content, sort_keys=True).encode()).hexdigest()


def _get_installed_python_version():  # type: () -> str
    return "{}.{}".format(sys.version_info.major, sys.version_info.minor)


def _validate_poetry_python_version(
    poetry_lock, current_python, debug=False
):  # type: (MutableMapping[str, Any], str, bool) -> None
    # TODO: Implement or use external parser for Python versions in Poetry specification.
    # See for details: https://github.com/thoth-station/micropipenv/issues/187
    wanted_python_version = poetry_lock["metadata"]["python-versions"]
    message = (
        "Warning: Currently, Micropipenv is not able to parse complex Python version specifications used by Poetry. "
        f"Desired version: {wanted_python_version}, current version: {current_python}."
    )
    level = "debug" if debug else "warning"
    getattr(_LOGGER, level)(message)


def verify_poetry_lockfile(
    pyproject=None, poetry_lock=None, current_python_version=None
):  # type: (Optional[MutableMapping[str, Any]], Optional[MutableMapping[str, Any]], Optional[str]) -> None
    """Validate that Poetry.lock is up to date with pyproject.toml."""
    if pyproject is None or poetry_lock is None:
        poetry_lock, pyproject = _read_poetry()
    if current_python_version is None:
        current_python_version = _get_installed_python_version()
    _validate_poetry_python_version(poetry_lock, current_python_version)
    pyproject_hash = _compute_poetry_hash(pyproject)
    poetry_lock_hash = poetry_lock["metadata"]["content-hash"]

    if pyproject_hash != poetry_lock_hash:
        raise HashMismatch(
            "Poetry.lock hash {!r} does not correspond to hash computed based on "
            "pyproject.toml {!r}, aborting deployment".format(poetry_lock_hash, pyproject_hash)
        )


def verify_pipenv_lockfile(
    pipfile=None, pipfile_lock=None
):  # type: (Optional[Dict[str, Any]], Optional[Dict[str, Any]]) -> None
    """Validate that Pipfile.lock is up to date with Pipfile."""
    pipfile_lock = pipfile_lock or _read_pipfile_lock()
    pipenv_python_version = pipfile_lock["_meta"].get("requires", {}).get("python_version")
    if pipenv_python_version is not None:
        installed_python_version = _get_installed_python_version()
        if pipenv_python_version != installed_python_version:
            raise PythonVersionMismatch(
                "Running Python version {}, but Pipfile.lock requires "
                "Python version {}".format(installed_python_version, pipenv_python_version)
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


def install_pipenv(
    pip_bin=_PIP_BIN, pipfile=None, pipfile_lock=None, *, deploy=False, dev=False, pip_args=None
):  # type: (str, Optional[Dict[str, Any]], Optional[Dict[str, Any]], bool, bool, Optional[List[str]]) -> None
    """Perform installation of packages from Pipfile.lock."""
    pipfile_lock = pipfile_lock or _read_pipfile_lock()
    _maybe_print_pipfile_lock(pipfile_lock)

    sections = get_requirements_sections(pipfile_lock=pipfile_lock, no_dev=not dev)
    if deploy:
        verify_pipenv_lockfile(pipfile, pipfile_lock)

    tmp_file = tempfile.NamedTemporaryFile("w", prefix="requirements_micropipenv-", suffix=".txt", delete=False)
    _LOGGER.debug("Using temporary file for storing requirements: %r", tmp_file.name)

    cmd = [pip_bin, "install", "--no-deps", "--disable-pip-version-check", "-r", tmp_file.name, *(pip_args or [])]
    _LOGGER.debug("Requirements will be installed using %r", cmd)

    packages = chain(
        sections.get("default", {}).items(),
        sections.get("develop", {}).items() if dev else [],
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

            if "git" in info:
                _LOGGER.warning("!!! Requirement %s uses a VCS version: %r", package_name, info)

            package_entry_str = _get_package_entry_str(package_name, info)
            for index_config_str in _iter_index_entry_str(sections, info):
                # We are opening the tmp_file for the second time here.
                # The purpose of this is to make sure that the content is always
                # flushed from buffers and that we start from the beggining
                # of the file every time. All of that to make sure that there is
                # only one package written in the tmp_file and pip is able to
                # read the package name from the file.
                with open(tmp_file.name, "w") as f:
                    f.write(index_config_str)
                    f.write(package_entry_str)

                _LOGGER.info("Installing %r", package_name)
                called_process = subprocess.run(cmd)

                if called_process.returncode == 0:
                    # Discard any error flag if we have any packages that fail to install.
                    for item in reversed(to_install):
                        if item["error"] == 0:
                            # Fast path - errors are always added to the end of the queue,
                            # if we find a package without any error we can safely break.
                            break
                        item["error"] = 0
                    break
            else:
                if len(to_install) == 0 or (had_error and had_error > len(to_install)):
                    raise PipInstallError(
                        "Failed to install requirements, dependency {!r} could not be installed".format(package_name)
                    )

                _LOGGER.warning("Failed to install %r, will try in next installation round...", package_name)
                to_install.append({"package_name": package_name, "info": info, "error": had_error + 1})

    finally:
        tmp_file.close()
        os.remove(tmp_file.name)


def _instantiate_package_finder(pip_session):  # type: (PipSession) -> PackageFinder
    """Instantiate package finder, in a pip>=10 and pip<10 compatible way."""
    try:
        return PackageFinder(find_links=[], session=pip_session, index_urls=_DEFAULT_INDEX_URLS)  # type: ignore
    except TypeError:  # API changed in pip>=10
        from pip._internal.models.search_scope import SearchScope
        from pip._internal.models.selection_prefs import SelectionPreferences

        selection_prefs = SelectionPreferences(
            allow_yanked=True,
        )

        additional_kwargs = {}
        if Version(pip_version).release >= (22, 3):
            # New argument in pip 22.3
            # https://github.com/pypa/pip/commit/5d7a1a68c7feb75136a0fd120de54b85df105bac
            additional_kwargs["no_index"] = False
        search_scope = SearchScope([], [], **additional_kwargs)  # type: ignore

        try:
            from pip._internal.index.collector import LinkCollector
        except ModuleNotFoundError:
            try:
                from pip._internal.collector import LinkCollector  # type: ignore
            except ModuleNotFoundError:  # pip>=19.2<20
                return PackageFinder.create(  # type: ignore
                    session=pip_session, selection_prefs=selection_prefs, search_scope=search_scope
                )

        link_collector = LinkCollector(session=pip_session, search_scope=search_scope)
        additional_kwargs = {}
        # pip 22 deprecates vendored html5lib and uses stdlib html.parser
        # https://github.com/pypa/pip/pull/10291
        # pip 22.2 will remove that switch
        # https://github.com/pypa/pip/issues/10825
        if (22, 2) > Version(pip_version).release >= (22,):
            additional_kwargs["use_deprecated_html5lib"] = False
        return PackageFinder.create(
            link_collector=link_collector,
            selection_prefs=selection_prefs,
            **additional_kwargs,  # type: ignore
        )


def _get_requirement_info(requirement):  # type: (ParsedRequirement) -> Dict[str, Any]
    """Get information about the requirement supporting multiple pip versions.

    This function acts like a compatibility layer across multiple pip releases supporting
    changes in pip's internal API to obtain information about requirements.
    """
    # Editable requirements.
    editable = getattr(requirement, "editable", False) or getattr(requirement, "is_editable", False)

    # Check for unsupported VCS.
    link_url = getattr(requirement, "requirement", None) or getattr(requirement, "link", None)
    if link_url and str(link_url).startswith(("hg+", "svn+", "bzr+")):
        raise NotSupportedError("Non-Git VCS requirement {!r} is not supported yet".format(str(link_url)))

    is_url = False
    req = None
    if hasattr(requirement, "req"):
        req = requirement.req  # type: ignore
    elif hasattr(requirement, "requirement") and not editable:
        if not requirement.requirement.startswith("git+"):
            req = Requirement(requirement.requirement)
        else:
            is_url = True

    # Link for requirements passed by URL or using path.
    link = None
    if editable:
        if hasattr(requirement, "link"):
            link = str(requirement.link)  # type: ignore
        elif req is not None:
            link = req.url
        elif hasattr(requirement, "requirement"):
            link = str(requirement.requirement)
        else:
            raise CompatibilityError

    # Requirement name.
    if editable:
        name = str(link)
    elif hasattr(requirement, "name"):
        name = requirement.name  # type: ignore
    elif req is not None:
        name = req.name
    elif hasattr(requirement, "requirement") and is_url:
        name = requirement.requirement
    else:
        raise CompatibilityError

    # Version specifier.
    version_specifier = None
    version_specifier_length = None
    if not editable and not is_url:
        if hasattr(requirement, "specifier"):
            version_specifier = str(requirement.specifier)  # type: ignore
            version_specifier_length = len(requirement.specifier)  # type: ignore
        elif req is not None:
            # pip>=20
            version_specifier = str(req.specifier)
            version_specifier_length = len(req.specifier)
        else:
            raise CompatibilityError

    # Artifact hashes.
    hash_options = None
    if not editable and not is_url:
        if hasattr(requirement, "options"):
            hash_options = requirement.options.get("hashes")  # type: ignore
        else:
            hash_options = requirement.hash_options  # type: ignore

    hashes = {}
    for hash_type, hashes_present in hash_options.items() if hash_options else []:
        hashes = {
            "hash_type": hash_type,
            "hashes_present": hashes_present,
        }

    # Markers.
    markers = None
    if not editable and not is_url:
        if hasattr(requirement, "markers"):
            markers = requirement.markers  # type: ignore
        elif req is not None:
            markers = req.marker
        else:
            raise CompatibilityError

    # Extras.
    extras = None
    if not editable and not is_url:
        if hasattr(requirement, "extras"):
            extras = requirement.extras  # type: ignore
        elif req is not None:
            extras = req.extras
        else:
            raise CompatibilityError

    return {
        "editable": editable,
        "version_specifier": version_specifier,
        "version_specifier_length": version_specifier_length,
        "hashes": hashes,
        "link": link,
        "extras": extras,
        "markers": markers,
        "name": name,
    }


def _requirements2pipfile_lock(requirements_txt_path=None):  # type: (Optional[str]) -> Dict[str, Any]
    """Parse requirements.txt file and return its Pipfile.lock representation."""
    requirements_txt_path = requirements_txt_path or _traverse_up_find_file("requirements.txt")

    pip_session = PipSession()
    finder = _instantiate_package_finder(pip_session)

    result = {}  # type: Dict[str, Any]
    for requirement in parse_requirements(filename=requirements_txt_path, session=PipSession(), finder=finder):
        requirement_info = _get_requirement_info(requirement)
        entry = {}  # type: Dict[str, Any]

        if not requirement_info["editable"]:
            if requirement_info["version_specifier"] is None or not (
                requirement_info["hashes"]
                and requirement_info["version_specifier_length"] == 1
                and requirement_info["version_specifier"].startswith("==")
            ):
                # Not pinned down software stack using pip-tools.
                raise PipRequirementsNotLocked

            hashes = []
            for hash_ in requirement_info["hashes"]["hashes_present"]:
                hashes.append("{}:{}".format(requirement_info["hashes"]["hash_type"], hash_))

            entry["hashes"] = sorted(hashes)
            entry["version"] = requirement_info["version_specifier"]
        else:
            entry["editable"] = True
            entry["path"] = requirement_info["link"]

        if requirement_info["extras"]:
            entry["extras"] = sorted(requirement_info["extras"])

        if requirement_info["markers"]:
            entry["markers"] = str(requirement_info["markers"])

        if entry.get("editable", False):
            # Create a unique name for editable to avoid possible clashes.
            requirement_name = hashlib.sha256(json.dumps(entry, sort_keys=True).encode("utf8")).hexdigest()
        else:
            requirement_name = requirement_info["name"]

        # We add all dependencies to default, develop should not be present in requirements.txt file, but rather
        # in dev-requirements.txt or similar.
        if requirement_name in result:
            raise RequirementsError("Duplicate entry for requirement {}".format(requirement.name))  # type: ignore

        result[requirement_name] = entry

    if all(dep.get("editable", False) for dep in result.values()):
        # If all the dependencies are editable, we cannot safely say that we
        # have a lock file - users can easily end up with missing dependencies
        # as we install dependencies with --no-deps in case of lock files. Let
        # pip resolver do its job, just to be sure.
        raise PipRequirementsNotLocked

    sources = []  # type: List[Dict[str, Any]]
    for index_url in chain(finder.index_urls, _DEFAULT_INDEX_URLS):
        if any(s["url"] == index_url for s in sources):
            continue

        sources.append({"name": hashlib.sha256(index_url.encode()).hexdigest(), "url": index_url, "verify_ssl": True})

    if len(sources) == 1:
        # Explicitly assign index if there is just one.
        for entry in result.values():
            if not entry.get("editable", False):
                entry["index"] = sources[0]["name"]

    with open(requirements_txt_path, "r") as requirements_file:
        requirements_hash = hashlib.sha256(requirements_file.read().encode()).hexdigest()

    return {
        "_meta": {
            "hash": {"sha256": requirements_hash},
            "pipfile-spec": 6,
            "sources": sources,
            "requires": {"python_version": _get_installed_python_version()},
        },
        "default": result,
        "develop": {},
    }


def _maybe_print_pipfile_lock(pipfile_lock):  # type: (Dict[str, Any]) -> None
    """Print and store Pipfile.lock based on configuration supplied."""
    if _NO_LOCKFILE_PRINT and _NO_LOCKFILE_WRITE:
        return

    pipfile_lock_json = json.dumps(pipfile_lock, sort_keys=True, indent=4)

    if not _NO_LOCKFILE_PRINT:
        print("-" * 33 + "- Pipfile.lock -" + "-" * 33, file=sys.stderr)
        print(pipfile_lock_json, file=sys.stderr)
        print("-" * 33 + "- Pipfile.lock -" + "-" * 33, file=sys.stderr)

    if not _NO_LOCKFILE_WRITE:
        try:
            with open("Pipfile.lock", "w") as lock_file:
                lock_file.write(pipfile_lock_json)
        except Exception as exc:
            _LOGGER.warning("Failed to write lockfile to container image: %s", str(exc))


def _maybe_print_pip_freeze(pip_bin):  # type: (str) -> None
    """Print and store requirements.txt based on configuration supplied."""
    if _NO_LOCKFILE_PRINT:
        return

    print("-" * 33 + "- pip freeze -" + "-" * 33, file=sys.stderr)
    cmd = [pip_bin, "freeze", "--disable-pip-version-check"]
    called_process = subprocess.run(cmd)
    print("-" * 33 + "- pip freeze -" + "-" * 33, file=sys.stderr)
    if called_process.returncode != 0:
        _LOGGER.warning("Failed to perform pip freeze to check installed dependencies, the error is not fatal")


def _translate_poetry_dependency(info):  # type: (str) -> str
    """Translate Poetry dependency specification as written in pyproject.toml into its Pipfile.lock equivalent."""
    if isinstance(info, str) and re.match(r"^\d", info):
        return "=={}".format(info)

    # TODO: poetry uses version like ^0.10.4 that are not Pipfile.lock complaint.
    return info


def _poetry2pipfile_lock(
    only_direct=False,
    no_default=False,
    no_dev=False,
    deploy=False,
):  # type: (bool, bool, bool, bool) -> Dict[str, Any]
    """Convert Poetry files to Pipfile.lock as Pipenv would produce."""
    poetry_lock, pyproject_toml = _read_poetry()

    current_python_version = _get_installed_python_version()
    if deploy:
        verify_poetry_lockfile(pyproject_toml, poetry_lock, current_python_version)
    else:
        _validate_poetry_python_version(poetry_lock, current_python_version, debug=True)

    pyproject_poetry_section = pyproject_toml.get("tool", {}).get("poetry", {})

    sources = []
    has_default = False  # If default flag is set, it disallows PyPI.
    for item in pyproject_poetry_section.get("source", []):
        source = {"name": item["name"], "verify_ssl": True}
        if item.get("url"):
            source["url"] = item.get("url")
        sources.append(source)

        has_default = has_default or item.get("default", False)

    for index_url in reversed(_DEFAULT_INDEX_URLS) if not has_default else []:
        # Place defaults as first.
        entry = {
            "url": index_url,
            "name": hashlib.sha256(index_url.encode()).hexdigest(),
            "verify_ssl": True,
        }  # type: Any
        sources.insert(0, entry)

    default: Dict[str, Any] = {}
    develop: Dict[str, Any] = {}

    if only_direct:
        if not no_default:
            for dependency_name, info in pyproject_poetry_section.get("dependencies", {}).items():
                if dependency_name != "python":
                    default[dependency_name] = _translate_poetry_dependency(info)

        if not no_dev:
            for dependency_name, info in pyproject_poetry_section.get("dev-dependencies", {}).items():
                develop[dependency_name] = _translate_poetry_dependency(info)

        return {
            "_meta": {
                "hash": {"sha256": poetry_lock["metadata"]["content-hash"]},
                "pipfile-spec": 6,
                "sources": sources,
                "requires": {"python_version": current_python_version},
            },
            "default": default,
            "develop": develop,
        }

    additional_markers = defaultdict(list)
    skip_all_markers = object()
    dev_category = set()
    main_category = set()

    normalized_pyproject_poetry_dependencies = [
        normalize_package_name(name) for name in pyproject_poetry_section.get("dependencies", ())
    ]

    normalized_pyproject_poetry_dev_dependencies = []

    groups = pyproject_poetry_section.get("group", {})
    for group, content in groups.items():
        if "dependencies" in content:
            normalized_pyproject_poetry_dev_dependencies.extend(
                [normalize_package_name(name) for name in content["dependencies"]]
            )

    # Double-ended queue for entries
    entries_queue = deque(poetry_lock["package"])
    # Record of attempts of getting a category of an entry
    # to potentially break endless loop caused by corrupted metadata.
    # Example: a package is in poetry.lock but it's neither direct
    # nor indirect dependency.
    entry_category_attempts = defaultdict(int)  # type: Dict[str, int]

    while entries_queue:
        entry = entries_queue.popleft()

        # Use normalized names everywhere possible.
        # Original name is needed for example for getting hashes from poetry.lock.
        original_name = entry["name"]
        entry["name"] = normalize_package_name(entry["name"])

        # Poetry 1.5+ no longer provides category in poetry.lock so we have to
        # guess it from the content of pyproject.toml and dependency graph.
        if entry.get("category") == "main" or entry["name"] in normalized_pyproject_poetry_dependencies:
            main_category.add(entry["name"])
        if entry.get("category") == "dev" or entry["name"] in normalized_pyproject_poetry_dev_dependencies:
            dev_category.add(entry["name"])
        if entry["name"] not in main_category and entry["name"] not in dev_category:
            # If we don't know the category yet, process the package later
            entry_category_attempts[entry["name"]] += 1
            if entry_category_attempts[entry["name"]] > 3:
                raise PoetryError(f"Failed to find package category for: {entry['name']}")
            entries_queue.append(entry)
            continue

        hashes = []
        # Older poetry.lock format contains files in [metadata].
        # New version 2.0 has files in [[package]] section.
        metadata_file_entries = poetry_lock["metadata"].get("files", {}).get(original_name, [])
        package_file_entries = entry.get("files", [])
        for file_entry in metadata_file_entries + package_file_entries:
            hashes.append(file_entry["hash"])

        requirement: Dict[str, Any] = {"version": "=={}".format(entry["version"])}

        if hashes:
            requirement["hashes"] = hashes

        if entry.get("marker"):
            requirement["markers"] = entry["marker"]

        if "source" in entry:
            if entry["source"]["type"] == "git":
                requirement["git"] = entry["source"]["url"]
                requirement["ref"] = entry["source"].get("resolved_reference", entry["source"]["reference"])
                try:
                    requirement["subdirectory"] = entry["source"]["subdirectory"]
                except KeyError:
                    pass
            elif entry["source"]["type"] == "directory":
                requirement["path"] = entry["source"]["url"]
            elif entry["source"]["type"] == "legacy":
                # Newer poetry marks packages using the old PyPI API as legacy.
                # If we have only one source, we can ignore it.
                # Otherwise, configure it explicitly.
                if len(sources) > 1:
                    requirement["index"] = entry["source"]["reference"]
            elif entry["source"]["type"] == "url":
                requirement["file"] = entry["source"]["url"]
            else:
                raise NotSupportedError(
                    "micropipenv supports Git VCS or directories, got {} instead".format(entry["source"]["type"])
                )

        # Poetry does not store information about extras in poetry.lock
        # (directly).  It stores extras used for direct dependencies in
        # pyproject.toml but it lacks this info being tracked for the
        # transitive ones. We approximate extras used - we check what
        # dependencies are installed as optional. If they form a set with all
        # dependencies present in specific extra, the given extra was used.
        extra_dependencies = set()

        for dependency_name, dependency_info in entry.get("dependencies", {}).items():
            dependency_name = normalize_package_name(dependency_name)
            if isinstance(dependency_info, dict):
                if dependency_info.get("optional", False):
                    extra_dependencies.add(dependency_name)

            # If the dependency is not direct and has some markers,
            # we should move the markers to the main dependency definition.
            # If there are no additional markers, we have to have a record
            # that the dependency has to be installed unconditionaly and that
            # we have to skip all other additional markers.
            # Also, we don't care about "extra" markers which are computed separatedly
            # and are usually not combined with other markers.
            if dependency_name not in normalized_pyproject_poetry_dependencies:
                if (
                    isinstance(dependency_info, dict)
                    and "markers" in dependency_info
                    and not dependency_info["markers"].startswith("extra")
                ):
                    additional_markers[dependency_name].append(dependency_info["markers"])
                else:
                    additional_markers[dependency_name].append(skip_all_markers)

            # If package fits into both main and dev categories, poetry add it to the main one.
            # This might be a problem in the following scenario:
            # Let's say our project looks like this:
            # dependencies:
            # - A
            # dev-dependencies:
            # - B
            #   - A (A is also a dependency of B)
            # Package A is therefore in the main category so if we use "--do-default" we get
            # only package B but no package A. But using requirements file requires to have
            # all dependencies with their hashes and pinned versions.
            # So, if a package is in dev and has a dependency in main, add the dependency also to dev or
            # if a package is already in "dev_category", add there also all its dependencies.
            if entry["name"] in dev_category:
                dev_category.add(dependency_name)

            # If this package is in main category, all of it's dependencies has to be
            # there as well.
            if entry["name"] in main_category:
                main_category.add(dependency_name)

        for extra_name, extras_listed in entry.get("extras", {}).items():
            # Turn requirement specification into the actual requirement name.
            all_extra_dependencies = set(Requirement(r.split(" ", maxsplit=1)[0]).name for r in extras_listed)
            if all_extra_dependencies.issubset(extra_dependencies):
                if "extras" not in requirement:
                    requirement["extras"] = []

                requirement["extras"].append(extra_name)

        # Sort extras to have always the same output.
        if "extras" in requirement:
            requirement["extras"] = sorted(requirement["extras"])

        if not no_default and entry["name"] in main_category:
            default[entry["name"]] = requirement

        if not no_dev and (entry["name"] in dev_category):
            develop[entry["name"]] = requirement

    for dependency_name, markers in additional_markers.items():
        # If a package depends on another package unconditionaly
        # we should skip all the markers for it.
        if skip_all_markers in markers:
            continue

        category: Optional[Dict[str, Any]]

        if dependency_name in default:
            category = default
        elif dependency_name in develop:
            category = develop
        else:
            category = None

        if category:
            all_markers = [category[dependency_name].get("markers", None), *markers]
            all_markers.remove(None)
            category[dependency_name]["markers"] = "(" + ") or (".join(sorted(all_markers)) + ")"

    if len(sources) == 1:
        # Explicitly assign index if there is just one.
        for entry in chain(default.values(), develop.values()):
            if "git" not in entry:
                entry["index"] = sources[0]["name"]

    return {
        "_meta": {
            "hash": {"sha256": poetry_lock["metadata"]["content-hash"]},
            "pipfile-spec": 6,
            "sources": sources,
            "requires": {"python_version": _get_installed_python_version()},
        },
        "default": default,
        "develop": develop,
    }


def install_poetry(
    pip_bin=_PIP_BIN, *, deploy=False, dev=False, pip_args=None
):  # type: (str, bool, bool, Optional[List[str]]) -> None
    """Install requirements from poetry.lock."""
    try:
        pipfile_lock = _poetry2pipfile_lock(deploy=deploy)
    except KeyError as exc:
        raise PoetryError("Failed to parse poetry.lock and pyproject.toml: {}".format(str(exc))) from exc
    install_pipenv(pip_bin, pipfile_lock=pipfile_lock, pip_args=pip_args, dev=dev, deploy=False)


def install_requirements(pip_bin=_PIP_BIN, *, pip_args=None):  # type: (str, Optional[List[str]]) -> None
    """Install requirements from requirements.txt."""
    requirements_txt_path = _traverse_up_find_file("requirements.txt")

    try:
        pipfile_lock = _requirements2pipfile_lock(requirements_txt_path)
        # Deploy set to false as there is no Pipfile to check against.
        install_pipenv(pip_bin, pipfile_lock=pipfile_lock, pip_args=pip_args, deploy=False)
    except PipRequirementsNotLocked:
        _LOGGER.warning("!" * 80)
        _LOGGER.warning("!!!")
        _LOGGER.warning("!!!\t\tProvenance and integrity of installed packages cannot be checked!")
        _LOGGER.warning("!!!")
        _LOGGER.warning("!!!\t\tThe provided requirements.txt file is not fully locked as not all dependencies are")
        _LOGGER.warning("!!!\t\tpinned to specific versions with digests of artifacts to be installed.")
        _LOGGER.warning("!!!")
        _LOGGER.warning("!" * 80)

        cmd = [pip_bin, "install", "-r", requirements_txt_path, "--disable-pip-version-check", *(pip_args or [])]
        _LOGGER.debug("Requirements will be installed using %r", cmd)
        called_process = subprocess.run(cmd)
        if called_process.returncode != 0:
            raise PipInstallError(
                "Failed to install requirements, it's highly recommended to use a lock file to "
                "to make sure correct dependencies are installed in the correct order"
            )

        _maybe_print_pip_freeze(pip_bin)


def method_discovery(ignore_files=None):  # type: (Optional[Sequence[str]]) -> str
    """Find the best method to use according to dependencies definition."""
    ignore_files = ignore_files if ignore_files else tuple()
    files = [f for f in _FILE_METHOD_MAP.keys() if f not in ignore_files]
    paths = []
    for file_name in files:
        try:
            paths.append(Path(_traverse_up_find_file(file_name)))
        except FileNotFound:
            pass

    if not paths:
        raise FileNotFound(
            "Failed to find {} "
            "in the current directory or any of its parent: {!r}".format(" or ".join(files), os.getcwd())
        )

    _LOGGER.debug("Dependencies definitions found: %s", paths)
    # The longest path means that we are as close to CWD as possible.
    # Sorting is also stable which means that two paths with the same
    # lenght will have the same order when sorted which keeps priorities
    # from _FILE_METHOS_MAP.
    longest_path = sorted(paths, key=lambda p: len(p.parts), reverse=True)[0]
    _LOGGER.debug("Choosen definition: %s", str(longest_path))

    return _FILE_METHOD_MAP[longest_path.name]


def verify(method=None):  # type: (Optional[str]) -> None
    """Check the lockfile to ensure it is up to date with the requirements file."""
    if method is None:
        method = method_discovery()

    if method == "pipenv":
        pipfile = _read_pipfile()
        pipfile_lock = _read_pipfile_lock()
        verify_pipenv_lockfile(pipfile, pipfile_lock)
        return
    elif method == "poetry":
        poetry_lock, pyproject = _read_poetry()
        verify_poetry_lockfile(pyproject, poetry_lock)
        return

    raise MicropipenvException("Unhandled method for checking lockfile: {}".format(method))


def install(
    method=None, *, pip_bin=_PIP_BIN, deploy=False, dev=False, pip_args=None
):  # type: (Optional[str], str, bool, bool, Optional[List[str]]) -> None
    """Perform installation of requirements based on the method used."""
    if method is None:
        method = method_discovery()

    if method == "requirements":
        if deploy:
            _LOGGER.debug("Discarding deploy flag when requirements.txt are used")

        if dev:
            _LOGGER.debug("Discarding dev flag when requirements.txt are used")

        install_requirements(pip_bin, pip_args=pip_args)
        return
    elif method == "pipenv":
        install_pipenv(pip_bin, deploy=deploy, dev=dev, pip_args=pip_args)
        return
    elif method == "poetry":
        install_poetry(pip_bin, pip_args=pip_args, deploy=deploy, dev=dev)
        return

    raise MicropipenvException("Unhandled method for installing requirements: {}".format(method))


def _parse_pipfile_dependency_info(pipfile_entry):  # type: (Union[str, Dict[str, Any]]) -> Dict[str, Any]
    """Parse a Pipfile entry for a package and return a compatible version with Pipfile.lock entry."""
    if isinstance(pipfile_entry, str):
        return {"version": pipfile_entry}
    elif isinstance(pipfile_entry, dict):
        return pipfile_entry

    raise ValueError("Unknown entry in Pipfile (should be of type dict or a str): {}".format(pipfile_entry))


def get_requirements_sections(
    *, pipfile=None, pipfile_lock=None, no_indexes=False, only_direct=False, no_default=False, no_dev=False
):  # type: (Optional[Dict[str, Any]], Optional[Dict[str, Any]], bool, bool, bool, bool) -> Dict[str, Any]
    """Compute requirements of an application, the output generated is compatible with pip-tools."""
    if no_dev and no_default:
        raise ArgumentsError("Cannot produce requirements as both, default and dev were asked to be discarded")

    result = {
        "default": {},
        "develop": {},
        "sources": [],
    }  # type: Dict[str, Any]

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
):  # type: (str, Union[Dict[str, Any], str], bool, bool) -> str
    """Print entry for the given package."""
    if isinstance(info, str):
        return package_name + info + "\n"

    if "git" in info:  # A special case for a VCS package
        if info.get("editable", False):
            result = "--editable git+{}".format(info["git"])
        else:
            result = "git+{}".format(info["git"])

        if "ref" in info:
            result += "@{}".format(info["ref"])
        result += "#egg={}".format(package_name)

        # The URL might contain a subdirectory like:
        # git+ssh://git@github.com/RidgeRun/gstd-1.x.git@v0.13.2#egg=pygstc\&subdirectory=libgstc/python
        if "subdirectory" in info:
            result += "&subdirectory={}".format(info["subdirectory"])

        return result + "\n"
    if "path" in info:
        # Path formats we want to support:
        # - "file:///path/to/project"
        # - "/path/to/project"
        # - "./path/to/project"
        # - "project" (== "./project")
        # - "."
        if "/" not in info["path"] and not info["path"].startswith("."):
            # Assume a relative path
            info["path"] = "./{}".format(info["path"])

    if info.get("editable", False):
        result = "--editable {}".format(info.get("path", "."))
    elif info.get("path", False):
        result = info["path"]
    else:
        result = package_name

    if info.get("file"):
        result = "{}#egg{}".format(info.get("file"), package_name)

    if info.get("extras"):
        result += "[{}]".format(",".join(info["extras"]))

    if not no_versions and info.get("version") and info["version"] != "*" and not info.get("path"):
        result += info["version"]

    if info.get("markers"):
        result += "; {}".format(info["markers"])

    if not (no_hashes or no_versions or info.get("editable", False)):
        for digest in info.get("hashes", []):
            result += " \\\n"
            result += "    --hash={}".format(digest)

    return result + "\n"


def _get_index_entry_str(sections, package_info=None):  # type: (Dict[str, Any], Optional[Dict[str, Any]]) -> str
    """Get configuration entry for Python package indexes."""
    index_name = package_info.get("index") if package_info is not None else None

    result = ""
    for idx, source in enumerate(sections.get("sources", [])):
        url = _resolve_nested_variables(source["url"])
        if index_name is None:
            if idx == 0:
                result += "--index-url {}\n".format(url)
            else:
                result += "--extra-index-url {}\n".format(url)

            if not source["verify_ssl"]:
                result += "--trusted-host {}\n".format(urlparse(url).netloc)
        else:
            if index_name == source["name"]:
                result += "--index-url {}\n".format(url)

                if not source["verify_ssl"]:
                    result += "--trusted-host {}\n".format(urlparse(url).netloc)

                break

    if index_name is not None and not result:
        raise RequirementsError(
            "No index found given the configuration: {} (package info: {})".format(sections, package_info)
        )

    return result


def _resolve_nested_variables(url):
    # type: (str) -> str
    while True:
        variable = __re_nested_vars.search(url)
        if not variable:
            break
        value = os.getenv(variable["name"])
        if not value:
            value = variable["default"] if variable["default"] else ""
        url = __re_sub_vars.sub(value, url, count=1)
    return url


def _iter_index_entry_str(
    sections, package_info
):  # type: (Dict[str, Any], Optional[Dict[str, Any]]) -> Generator[str, None, None]
    """Iterate over possible package index configurations for the given package to try all possible installations."""
    index_name = package_info.get("index") if package_info is not None else None

    if index_name is not None or len(sections.get("sources") or []) <= 1:
        # No need to iterate over indexes, the package index is set and is just one.
        res = _get_index_entry_str(sections, package_info)
        yield from [res]
        return None

    for source in sections["sources"]:
        source["url"] = _resolve_nested_variables(source["url"])
        result = "--index-url {}\n".format(source["url"])
        if not source["verify_ssl"]:
            result += "--trusted-host {}\n".format(urlparse(source["url"]).netloc)

        yield result


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

    included = set()

    if not no_comments and sections.get("default"):
        result += "#\n# Default dependencies\n#\n"

    for package_name, info in sections.get("default", {}).items():
        if package_name in included:
            continue
        else:
            included.add(package_name)

        result += _get_package_entry_str(package_name, info, no_versions=no_versions, no_hashes=no_hashes)

    if not no_comments and sections.get("develop"):
        result += "#\n# Dev dependencies\n#\n"

    for package_name, info in sections.get("develop", {}).items():
        if package_name in included:
            continue
        else:
            included.add(package_name)

        result += _get_package_entry_str(package_name, info, no_versions=no_versions, no_hashes=no_hashes)

    return result


def requirements(
    method=None,
    sections=None,
    *,
    no_hashes=False,
    no_indexes=False,
    no_versions=False,
    only_direct=False,
    no_default=False,
    no_dev=False,
    no_comments=False,
):  # type: (Optional[str], Optional[Dict[str, Any]], bool, bool, bool, bool, bool, bool, bool) -> None
    """Show requirements of an application, the output generated is compatible with pip-tools."""
    if method is None:
        method = method_discovery(ignore_files=("requirements.txt",))

    if method == "pipenv":
        sections = sections or get_requirements_sections(
            no_indexes=no_indexes, only_direct=only_direct, no_default=no_default, no_dev=no_dev
        )
    elif method == "poetry":
        sections = _poetry2pipfile_lock(only_direct=only_direct, no_default=no_default, no_dev=no_dev)
    else:
        raise MicropipenvException("Unhandled method for installing requirements: {}".format(method))

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
    """Micropipenv Main Function."""
    argv = argv or sys.argv[1:]

    parser = argparse.ArgumentParser(prog=__title__, description=__doc__)
    parser.add_argument("--version", help="Print version information and exit.", action="version", version=__version__)
    parser.add_argument("--verbose", action="count", help="Increase verbosity, can be supplied multiple times.")

    subparsers = parser.add_subparsers()

    parser_verify = subparsers.add_parser("verify", help=verify.__doc__)
    parser_verify.add_argument(
        "--method",
        help="Source of packages for the installation, perform detection if not provided.",
        choices=["pipenv", "poetry"],
        default=os.getenv("MICROPIPENV_METHOD"),
    )
    parser_verify.set_defaults(func=verify)

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
        "--method",
        help="Source of packages for the installation, perform detection if not provided.",
        choices=["pipenv", "requirements", "poetry"],
        default=os.getenv("MICROPIPENV_METHOD"),
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
    parser_requirements.add_argument(
        "--method",
        help="Source of packages for the requirements file, perform detection if not provided.",
        choices=["pipenv", "poetry"],
        default=os.getenv("MICROPIPENV_METHOD", "pipenv"),
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
    try:
        return_code = main()
    except Exception:
        _check_pip_version(raise_on_incompatible=False)
        raise
    else:
        sys.exit(return_code)
