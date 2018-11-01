import os
from pathlib import Path

import time
from fabric.colors import blue, green, yellow
from fabric.context_managers import hide, settings, cd
from fabric.decorators import task, hosts, parallel
from fabric.operations import local, run
from fabric.state import env
from fabric.tasks import execute
from fabric.utils import abort, puts
from default_settings_to_json_file import export_default_settings_to_json_file

SOLIUM_VERSION = '0.2.2'
HERE = Path().resolve()
REQ_DIR = HERE / 'requirements'

env.use_ssh_config = True
env.hosts = [
    'root@207.154.205.41',
    'gsy@gsy-d3a-demo.local',
]

HOST_CONFIG = {
    '207.154.205.41': {
        'port': "9000",
        'session_name': "d3a",
        'd3a_options': "-t 30s --paused",
        'trigger_pause': True
    },
    'gsy-d3a-demo.local': {
        'port': "5000",
        'session_name': "simulation",
        'd3a_options': "-t 10s --slowdown 5 --reset-on-finish --reset-on-finish-wait 10s",
        'trigger_pause': False
    },
}

HOST_CONFIG['10.51.21.251'] = HOST_CONFIG['gsy-d3a-demo.local']


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


def _ensure_pre_commit():
    hook_dir = Path(".git/hooks")
    hook = hook_dir.joinpath('pre-commit')
    captainhook_installed = False
    pre_commit_installed = False
    if hook.exists():
        captainhook_installed = ("CAPTAINHOOK IDENTIFIER" in hook.read_text())
    if captainhook_installed:
        puts(yellow("Removing obsolete captainhook"))
        checkers_dir = hook_dir.joinpath('checkers')
        for file in checkers_dir.glob("*"):
            file.unlink()
        checkers_dir.rmdir()
    if not pre_commit_installed:
        puts(yellow("Configuring 'pre-commit' git hooks"))
        with hide('running', 'stdout'):
            local("pre-commit install --overwrite")
    else:
        with hide('running', 'stdout'):
            local("pre-commit autoupdate")


def _ensure_venv():
    if 'VIRTUAL_ENV' not in os.environ:
        abort('No active virtualenv found. Please create / activate one before continuing.')


def _ensure_pip_tools():
    try:
        import piptools  # noqa
    except ImportError:
        with hide('running', 'stdout'):
            puts(yellow("Installing 'pip-tools'"), show_prefix=True)
            local("pip install pip-tools")


def _ensure_ganache_cli():
    error_code = os.system('ganache-cli --version > /dev/null')
    if error_code != 0:
        local('npm install --global ganache-cli')


def _ensure_solidity_compiler():
    solidity_version = local('solc --version')
    # Smart contracts depend on solc v0.4.25
    if "0.4.25" not in solidity_version:
        local('brew install https://raw.githubusercontent.com/ethereum/'
              'homebrew-ethereum/f26f126820e5f47c3ed7ec6d5e6e046707443d87/solidity.rb')


def _pre_check():
    _ensure_venv()
    with hide('running', 'stdout'):
        # Temporary until pyethereum is installable with setuptools >= 38.0.0
        # (should be after 2.2.0)
        local("pip install 'setuptools<38.0.0'")
    _ensure_pip_tools()


def _post_check():
    _ensure_solium()
    _ensure_ganache_cli()
    _ensure_solidity_compiler()
    _ensure_pre_commit()


@task
@hosts('localhost')
def compile(upgrade="", package=None):
    """Update list of requirements"""
    if upgrade and package:
        abort("Can only specify one of `upgrade` or `package`")
    if package:
        puts(blue("Upgrading spec for {}".format(package)))
    elif upgrade:
        puts(blue("Upgrading all package specs"))
    _pre_check()
    upgrade = (upgrade.lower() in {'true', 'upgrade', '1', 'yes', 'up'})
    with hide('running', 'stdout'):
        puts(green("Updating requirements"), show_prefix=True)
        for file in REQ_DIR.glob('*.in'):
            puts(blue("  - {}".format(file.name.replace(".in", ""))))
            local('pip-compile --no-index {}{} --rebuild {}'.format(
                '--upgrade' if upgrade or package else '',
                '-package {}'.format(package) if package else '',
                file.relative_to(HERE)
            ))


@task(default=True)
@hosts('localhost')
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

    export_default_settings_to_json_file()


@task
@hosts('localhost')
def reqs():
    """'compile' then 'sync'"""
    execute(compile)
    execute(sync)


@task()
@parallel
def deploy():
    conf = HOST_CONFIG[env.host]
    with cd('d3a'):
        run("git pull")
        run("docker build -t d3a .")
        with settings(warn_only=True):
            run("docker stop d3a")
        run('tmux new -d -s {c[session_name]} '
            '"docker run --rm --name d3a -it -p {c[port]}:5000 -v $(pwd)/.d3a:/app/.d3a '
            'd3a -l ERROR run {c[d3a_options]}"'.format(c=conf))
        time.sleep(5)
        if conf['trigger_pause']:
            run("curl -X POST http://localhost:{c[port]}/api/pause".format(c=conf))
