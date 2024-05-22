"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
import sys
from pathlib import Path

from fabric.connection import Connection
from fabric.tasks import task


HERE = Path().resolve()
REQ_DIR = HERE / "requirements"

cnx = Connection("localhost")


def _ensure_pre_commit():
    hook_dir = Path(".git/hooks")
    hook = hook_dir.joinpath("pre-commit")
    captainhook_installed = False
    pre_commit_installed = False
    if hook.exists():
        captainhook_installed = "CAPTAINHOOK IDENTIFIER" in hook.read_text(encoding="utf-8")
    if captainhook_installed:
        print("Removing obsolete captainhook")
        checkers_dir = hook_dir.joinpath("checkers")
        for file in checkers_dir.glob("*"):
            file.unlink()
        checkers_dir.rmdir()
    if not pre_commit_installed:
        print("Configuring 'pre-commit' git hooks")
        cnx.local("pre-commit install --overwrite", hide=True)
    else:
        cnx.local("pre-commit autoupdate", hide=True)


def _ensure_venv():
    if "VIRTUAL_ENV" not in os.environ:
        sys.exit("No active virtualenv found. Please create / activate one before continuing.")


def _ensure_pip_tools():
    try:
        # pylint: disable=import-outside-toplevel,unused-import
        import piptools  # noqa
    except ImportError:
        print("Installing 'pip-tools'")
        cnx.local("pip install pip-tools", hide=True)


def _pre_check():
    _ensure_venv()
    _ensure_pip_tools()


def _fab_compile_requirements_file(file, upgrade, package):
    print(f"  - {file.name.replace('.in', '')}")
    upgrade_option = "--upgrade" if upgrade or package else ""
    package_option = f"-package {package}" if package else ""
    cnx.local(f"pip-compile --max-rounds 100 --no-emit-index-url "
              f"{upgrade_option}{package_option} "
              f"--rebuild {file.relative_to(HERE)}")


@task(hosts=["localhost"])
def compile_requirements(_ctx, upgrade="", package=None):
    """Update list of requirements."""

    if upgrade and package:
        sys.exit("Can only specify one of `upgrade` or `package`")
    if package:
        print(f"Upgrading spec for {package}")
    elif upgrade:
        print("Upgrading all package specs")
    _pre_check()
    upgrade = upgrade.lower() in {"true", "upgrade", "1", "yes", "up"}
    print("Updating requirements")
    cnx.local(f"rm -rf {REQ_DIR / 'base.txt'}")
    cnx.local(f"rm -rf {REQ_DIR / 'dev.txt'}")
    cnx.local(f"rm -rf {REQ_DIR / 'tests.txt'}")
    _fab_compile_requirements_file(REQ_DIR / "base.in", upgrade, package)
    _fab_compile_requirements_file(REQ_DIR / "dev.in", upgrade, package)
    _fab_compile_requirements_file(REQ_DIR / "tests.in", upgrade, package)


@task(hosts=["localhost"], default=True)
def sync(ctx):
    """Ensure installed packages match requirements."""
    _pre_check()
    print("Syncing requirements to local packages")
    joined_req_paths = " ".join(
        str(f.relative_to(HERE))
        for f in REQ_DIR.glob("*.txt")
    )
    cnx.local(f"pip-sync {joined_req_paths}", hide=True)
    cnx.local("pip install -e .", hide=True)
    _ensure_pre_commit()
    write_default_settings_file(ctx)


@task(hosts=["localhost"])
def build_all(ctx):
    """Build everything, including recompiling the dependencies and installing them locally."""
    compile_requirements(ctx)
    sync(ctx)


@task(hosts=["localhost"])
def write_default_settings_file(_ctx):
    """Fab task that creates or updates the default settings file."""
    # This lazy import has stay in order to avoid import errors when running 'fab sync'
    # pylint: disable=import-outside-toplevel
    from gsy_e.gsy_e_core.util import export_default_settings_to_json_file
    export_default_settings_to_json_file()
