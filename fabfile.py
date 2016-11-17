import os
from functools import wraps
from pathlib import Path

import sys
from fabric.colors import blue, green, yellow
from fabric.context_managers import hide
from fabric.decorators import task
from fabric.operations import local
from fabric.tasks import execute
from fabric.utils import abort, puts


HERE = Path().resolve()
REQ_DIR = HERE / 'requirements'

_ENV_CHECKED = False


def _pre_check():
    if 'VIRTUAL_ENV' not in os.environ:
        abort('No active virtualenv found. Please create / activate one before continuing.')
    try:
        import piptools  # noqa
    except ImportError:
        with hide('running', 'stdout'):
            puts(yellow("Installing 'pip-tools'"), show_prefix=True)
            local("pip install pip-tools")


def _post_check():
    hook = Path(".git/hooks/pre-commit")
    captainhook_installed = False
    if hook.exists():
        captainhook_installed = ("CAPTAINHOOK IDENTIFIER" in hook.read_text())
    if not captainhook_installed:
        puts(yellow("Configuring 'captainhook' git pre-commit hooks"))
        with hide('running', 'stdout'):
            local("captainhook install")
        # Patch virtualenv path
        # See https://github.com/alexcouper/captainhook/pull/109
        with hook.open('r+') as hook_file:
            content = hook_file.readlines()
            content[0] = "#!{}\n".format(sys.executable)
            hook_file.seek(0)
            hook_file.write("".join(content))
            hook_file.truncate()


def ensure_env(func):
    @wraps(func)
    def check(*args, **kwargs):
        global _ENV_CHECKED
        if not _ENV_CHECKED:
            _pre_check()
        ret = func(*args, **kwargs)
        if not _ENV_CHECKED:
            _post_check()
        _ENV_CHECKED = True
        return ret

    return check


@task
@ensure_env
def compile():
    """Update list of requirements"""
    with hide('running', 'stdout'):
        puts(green("Updating requirements"), show_prefix=True)
        for file in REQ_DIR.glob('*.in'):
            puts(blue("  - {}".format(file.name.replace(".in", ""))))
            local('pip-compile --no-index --rebuild {0}'.format(file.relative_to(HERE)))


@task(default=True)
@ensure_env
def sync():
    """Ensure installed packages match requirements"""
    with hide('running'):
        puts(green("Syncing requirements to local packages"), show_prefix=True)
        local(
            'pip-sync {}'.format(
                " ".join(
                    str(f.relative_to(HERE))
                    for f in REQ_DIR.glob('*.txt')
                )
            )
        )
        local('pip install --no-deps -e .')


@task
def reqs():
    """'compile' then 'sync'"""
    execute(compile)
    execute(sync)
