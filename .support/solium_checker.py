"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
