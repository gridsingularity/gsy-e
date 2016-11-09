from fabric.context_managers import lcd
from fabric.decorators import task
from fabric.operations import local
from pathlib import Path

from fabric.tasks import execute


HERE = Path().resolve()
REQ_DIR = HERE / 'requirements'


@task
def compile_reqs():
    local("pip -q install pip-tools")
    for file in REQ_DIR.glob('*.in'):
        local('pip-compile --no-index {0}'.format(file.relative_to(HERE)))

    # Remove absolute path references from compile results
    # See https://github.com/nvie/pip-tools/issues/204
    here = "file://{}".format(str(HERE.resolve()))
    for file in REQ_DIR.glob('*.txt'):
        lines = [l.replace(here, ".").strip() for l in file.read_text().split('\n')]
        file.write_text("\n".join(lines))


@task
def sync_reqs():
    local("pip -q install pip-tools")
    local('pip-sync {}'.format(" ".join(str(f.relative_to(HERE)) for f in REQ_DIR.glob('*.txt'))))


@task
def reqs():
    execute(compile_reqs)
    execute(sync_reqs)
