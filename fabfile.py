import os
import shutil
from pathlib import Path

from fabric.colors import blue, green, yellow
from fabric.context_managers import hide, settings
from fabric.decorators import task
from fabric.operations import local
from fabric.tasks import execute
from fabric.utils import abort, puts


SOLIUM_VERSION = '0.2.1'
HERE = Path().resolve()
REQ_DIR = HERE / 'requirements'


def _ensure_solium():
    with settings(hide('everything'), warn_only=True):
        r = local('solium --version', capture=True)
        installed_version = r.stdout.strip()
        if r.return_code == 0 and installed_version == SOLIUM_VERSION:
            return
        r = local('npm --version', capture=True)
        if r.return_code != 0:
            abort("The 'npm' package manager is missing, please install it.\n"
                  "See: https://docs.npmjs.com/getting-started/installing-node")
        r = local('npm root --global', capture=True)
    solium_path = Path(r.stdout.strip()).joinpath('solium')
    if not solium_path.exists() or installed_version != SOLIUM_VERSION:
        puts(yellow("Installing 'solium' solidity linter"))
        with hide('running', 'stdout'):
            local("npm install --global solium@{}".format(SOLIUM_VERSION))

        # Grr, patch https://github.com/duaraghav8/Solium/issues/53
        with solium_path.joinpath('lib', 'rules', 'operator-whitespace.js').open('r+') as f:
            content = f.readlines()
            for i, line in enumerate(content):
                if "var strBetweenLeftAndRight" in line:
                    content.insert(i, "if (node.left.type == 'BinaryExpression') { return; }\n")
                    break
            f.seek(0)
            f.write("".join(content))
            f.truncate()


def _ensure_captainhook():
    hook = Path(".git/hooks/pre-commit")
    captainhook_installed = False
    if hook.exists():
        captainhook_installed = ("CAPTAINHOOK IDENTIFIER" in hook.read_text())
    if not captainhook_installed:
        puts(yellow("Configuring 'captainhook' git pre-commit hooks"))
        with hide('running', 'stdout'):
            local("captainhook install --use-virtualenv-python")
    shutil.copy('.support/solium_checker.py', '.git/hooks/checkers/')


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
    _ensure_solium()
    _ensure_captainhook()


@task
def compile():
    """Update list of requirements"""
    _pre_check()
    with hide('running', 'stdout'):
        puts(green("Updating requirements"), show_prefix=True)
        for file in REQ_DIR.glob('*.in'):
            puts(blue("  - {}".format(file.name.replace(".in", ""))))
            local('pip-compile --no-index --rebuild {0}'.format(file.relative_to(HERE)))


@task(default=True)
def sync():
    """Ensure installed packages match requirements"""
    _pre_check()
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
    _post_check()


@task
def reqs():
    """'compile' then 'sync'"""
    execute(compile)
    execute(sync)
