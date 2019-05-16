====================================
d3a: Decentralized Autonomous Area Agent
====================================

The D3A is a blockchain-based, distributed energy market model developed by Grid Singularity with
the objective of supporting the Energy Web Foundation (EWF) mission to enable a decarbonized,
decentralized, democratized and digitized energy system.


Code of Conduct
===============
Please refer to: https://github.com/gridsingularity/d3a/blob/master/CODE_OF_CONDUCT.md

How to contribute:
==================
Please refer to: https://github.com/gridsingularity/d3a/blob/master/CONTRIBUTING.md


Basic setup
===========

(For instructions using `Docker`_ see below)

After cloning this project setup a Python 3.6 virtualenv and install `fabric3`_::

    ~# pip install fabric3


To install solidity follow the steps here:

https://solidity.readthedocs.io/en/v0.5.1/installing-solidity.html#binary-packages

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

    ~# docker run --rm -it d3a


Command line parameters can be given normally after the image name::

    ~# docker run --rm d3a --help
    ~# docker run --rm d3a run --help
    ~# docker run --rm d3a run --setup default_2a -t15s


There is also a handy script that deals with the building of the image and running the provided command::

    ~# ./run_d3a_on_docker.sh "$docker_command" $export_path


where you can provide the d3a_command and export path where the simulation results are stored.
For example::

    ~# ./run_d3a_on_docker.sh "d3a -l ERROR run --setup default_2a -t 15s" $HOME/d3a-simulation


builds a d3a docker image (if not already present),
runs the simulation with setup-file default_2a, tick-length 15s
and stores the simulation output data into $HOME/d3a-simulation.
If no export_path is provided, simulation results will be stored in $HOME/d3a-simulation.


_`docker`: https://docker.io


Detailed Documentation
===============
Please refer to: https://gridsingularity.atlassian.net/wiki/spaces/D3AD/pages/855212151/D3A+Documentation
