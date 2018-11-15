====================================
d3a: GridSingularity AreaManager PoC
====================================

The D3A is a blockchain-based, distributed energy market model developed by Grid Singularity with
the objective of supporting the Energy Web Foundation (EWF) mission to enable a decarbonized,
decentralized, democratized and digitized energy system.

See whitepaper here: <https://to-be-replaced-by-the-real.url>


Basic setup
===========

(For instructions using `Docker`_ see below)

After cloning this project setup a Python 3.5 virtualenv and install `fabric3`_::

    ~# pip install fabric3

To install the dependencies run the following command::

    ~# fab sync



The Simulation
==============

Running the simulation
----------------------

After installation the simulation can be run with the following command::

    ~# d3a run

There are various options available to control the simulation run.
Help on there is available via::

    ~# d3a run --help


Controlling the simulation
--------------------------

During a simulation run the following keyboard commands are available:

=== =======
Key Command
=== =======
i   Show information about simulation
p   Pause simulation
q   Quit simulation
r   Reset and restart simulation
R   Start a Python REPL at the current simulation step
s   Save current state of simulation to file (see below for resuming)
`+` Increase 'slowdown' factor
`-` Decrease 'slowdown' factor
=== =======

All of these commands are also available via the `REST-API`_ (see below).


Resuming a previously saved run
-------------------------------

To resume a previously saved simulation state use the `resume` subcommand::

    ~# d3a resume <save-file>



Development
===========

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


Docker
------

The repository contains a `docker`_ Dockerfile. To build an image use the
following command (change into repository folder first)::

    ~# docker build -t d3a .


After building is complete you can run the image with::

    ~# docker run --rm -it -p 5000:5000 -v $(pwd)/.d3a:/app/.d3a d3a


Command line parameters can be given normally after the image name::

    ~# docker run --rm -it -p 5000:5000 -v $(pwd)/.d3a:/app/.d3a d3a --help
    ~# docker run --rm -it -p 5000:5000 -v $(pwd)/.d3a:/app/.d3a d3a run --help
    ~# docker run --rm -it -p 5000:5000 -v $(pwd)/.d3a:/app/.d3a d3a run --setup default_2a -t15s


_`docker`: https://docker.io


REST-API
========

The application provides a rest API (listening on http://localhost:5000/api by
default).

The API contains a browsable HTML interface that is shown by default when
accessing the endpoints via a browser. Otherwise JSON is returned.

All places in the API where energy values are shown negative values denote
bought energy and positive ones sold energy.

The structure is as follows::

    /api                                [GET]
      |
      -/pause                           [GET, POST]
      |
      -/reset                           [POST]
      |
      -/save                            [POST]
      |
      -/slowdown                        [GET, POST]
      |
      -/<area-slug>                     [GET]
         |
         -/markets                      [GET]
         |
         -/market/<absolute-timestmap>  [GET]
         |
         -/market/<relative-time>       [GET]
         |
         -/trigger/<trigger-name>       [POST]


The top level (`/api`) returns a summary of the simulation configuration as
well as the area structure.

There are four endpoints to control the simulation. In details these are:

======== =======
Endpoint Purpose
======== =======
pause    Pause / unpause the simulation
reset    Reset the simulation and restart the current run
save     Save the current state of the simulation to a file
slowdown Adjust 'slowdown' parameter to control the simulation speed
======== =======

The `/<area-slug>` endpoints contains genral information about the area in
question as well as lists all markets this area contains.

The `/<area-slug>/markets` endpoint returns an abbreviated overview of all
markets with aggregated data per market.

Detailed information about a market including all offers and trades is
available at the `/<area-slug>/market/<absolute-timestmap>` and
`/<area-slug>/market/<relative-time>` endpoints.

The `/<area-slug>/trigger/<trigger-name>` endpoints allow triggering events
within the areas. Which events are available is listed in the corresponding
`/<area-slug>` endpoint under the `available_triggers` key.

The absolute timestamps are what is linked from the `url` fields of the various
other endpoints. They are of the form 'YYYY-MM-DDTHH:MM:SS+01:00' where the
date part is the current day and the time the simulated market time slot.

The relative adressing allows to always specify a market relative to the
'current' simulation time. The allowed values are:

* negative integers - Returns the "past" markets in decending order (most
  recent first)
* the string 'current' - Returns the currently executing market
* positive integers - Returns future markets in ascending order (zero based)
