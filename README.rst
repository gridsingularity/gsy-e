d3a: GridSingularity AreaManager PoC
====================================

Dev environment
---------------

After cloning this project setup a Python 3.5 virtualenv and install `fabric3`_::

    ~# pip install fabric3

To install the dependencies run the following command::

    ~# fab sync



Updating requirements
---------------------

We use `pip-tools`_ managed by `fabric3`_ to handle requirements.
To update the pinned requirements use the following command::

    ~# fab compile



There is also a command to compile and sync in one step::

    ~# fab reqs


_`pip-tools`: https://github.com/nvie/pip-tools
_`fabric3`: https://pypi.python.org/pypi/Fabric3


Development model
-----------------

For everything that goes beyond fixing typos or simple whitespace changes we
use feature branches and corresponding PRs on Github.

To start work on something new create a branch of the form
`feature/<feature_name>`, push it to Github and create a PR for this branch.
If it's not yet ready to be merged please mark it with `WIP` in the title of
the PR.

Before merging, PRs should be reviewed by another team member.

Please write tests for new features (see below) and ensure that we maintain a
decent test coverage. Currently `coverage.py`_ is configured to require a
coverage of 80% or greater.

_`coverage.py`: https://coverage.rtfd.org


Testing
-------

We use `py.test`_ managed by `tox`_ to run the (unit) tests.
To run the test suite simply run the following command::

    ~# tox


_`py.test`: https://pytest.org
_`tox`: https://tox.testrun.org
