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
from pathlib import Path

from fabric.colors import blue, green, yellow
from fabric.context_managers import hide
from fabric.decorators import task, hosts
from fabric.operations import local
from fabric.tasks import execute
from fabric.utils import abort, puts

HERE = Path().resolve()
REQ_DIR = HERE / "requirements"


def _ensure_pre_commit():
    hook_dir = Path(".git/hooks")
    hook = hook_dir.joinpath("pre-commit")
    captainhook_installed = False
    pre_commit_installed = False
    if hook.exists():
        captainhook_installed = ("CAPTAINHOOK IDENTIFIER" in hook.read_text())
    if captainhook_installed:
        puts(yellow("Removing obsolete captainhook"))
        checkers_dir = hook_dir.joinpath("checkers")
        for file in checkers_dir.glob("*"):
            file.unlink()
        checkers_dir.rmdir()
    if not pre_commit_installed:
        puts(yellow("Configuring 'pre-commit' git hooks"))
        with hide("running", "stdout"):
            local("pre-commit install --overwrite")
    else:
        with hide("running", "stdout"):
            local("pre-commit autoupdate")


def _ensure_venv():
    if "VIRTUAL_ENV" not in os.environ:
        abort("No active virtualenv found. Please create / activate one before continuing.")


def _ensure_pip_tools():
    try:
        import piptools  # noqa
    except ImportError:
        with hide("running", "stdout"):
            puts(yellow("Installing 'pip-tools'"), show_prefix=True)
            local("pip install pip-tools")


def _pre_check():
    _ensure_venv()
    _ensure_pip_tools()


def fab_compile_requirements_file(file, upgrade, package):
    puts(blue("  - {}".format(file.name.replace(".in", ""))))
    local("pip-compile --max-rounds 100 --no-emit-index-url {}{} --rebuild {}".format(
        "--upgrade" if upgrade or package else "",
        "-package {}".format(package) if package else "",
        file.relative_to(HERE)
    ))


@task
@hosts("localhost")
def compile(upgrade="", package=None):
    """Update list of requirements"""

    if upgrade and package:
        abort("Can only specify one of `upgrade` or `package`")
    if package:
        puts(blue("Upgrading spec for {}".format(package)))
    elif upgrade:
        puts(blue("Upgrading all package specs"))
    _pre_check()
    upgrade = (upgrade.lower() in {"true", "upgrade", "1", "yes", "up"})
    with hide("running", "stdout"):
        puts(green("Updating requirements"), show_prefix=True)
        fab_compile_requirements_file(REQ_DIR / "base.in", upgrade, package)
        fab_compile_requirements_file(REQ_DIR / "dev.in", upgrade, package)
        fab_compile_requirements_file(REQ_DIR / "tests.in", upgrade, package)


@task(default=True)
@hosts("localhost")
def sync():
    """Ensure installed packages match requirements"""
    _pre_check()
    with hide("running"):
        puts(green("Syncing requirements to local packages"), show_prefix=True)
        local(
            "pip-sync {}".format(
                " ".join(
                    str(f.relative_to(HERE))
                    for f in REQ_DIR.glob("*.txt")
                )
            )
        )
        local("pip install -e .")
    _ensure_pre_commit()
    write_default_settings_file()


@task
@hosts("localhost")
def reqs():
    """'compile' then 'sync'"""
    execute(compile)
    execute(sync)


@task
@hosts("localhost")
def write_default_settings_file():
    # This lazy import has stay in order to avoid import errors when running 'fab sync'
    from gsy_e.gsy_e_core.util import export_default_settings_to_json_file
    export_default_settings_to_json_file()
