# This file will be installed to .git/hooks/checkers by `fab sync`
from .utils import bash

CHECK_NAME = 'solium'
REQUIRED_FILES = ['.soliumrc.json', '.soliumignore']


def run(files):
    errors = []
    for file_name in files:
        if file_name.endswith(".sol"):
            out = bash("solium --file {}".format(file_name)).value()
            if out:
                errors.append(out)
    if errors:
        return "\n".join(errors)
    return False
