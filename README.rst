====================================
Grid Singularity Energy Exchange
====================================

.. image:: https://codecov.io/gh/gridsingularity/d3a/branch/master/graph/badge.svg?token=XTWK3DAKUA
   :target: https://codecov.io/gh/gridsingularity/d3a

The Grid Singularity Energy Exchange Engine is developed by `Grid Singularity <https://gridsingularity.com/>`__ as an interface (`Singularity Map <https://map.gridsingularity.com/singularity-map>`__) and open source codebase (see `Licensing <https://gridsingularity.github.io/d3a/licensing/>`__ to model, simulate, optimize and (coming soon) download and deploy interconnected, grid-aware energy marketplaces.
Grid Singularity has been proclaimed the `World Tech Pioneer by the World Economic Forum <https://www.weforum.org/organizations/grid-singularity-gmbh-gsy-gmbh>`__ and is also known as a co-founder of the `Energy Web Foundation <https://www.energyweb.org/>`__ that gathers leading energy corporations globally co-developing a shared blockchain-based platform.

Code of Conduct
===============
Please refer to: https://github.com/gridsingularity/d3a/blob/master/CODE_OF_CONDUCT.md

How to contribute:
==================
Please refer to: https://github.com/gridsingularity/d3a/blob/master/CONTRIBUTING.md


Basic setup
===========

(For instructions using `Docker`_ see below)

After cloning this project setup a Python 3.8 virtualenv and install `fabric3`_::

    ~# pip install fabric3


The Simulation
==============

Running the simulation
----------------------

After installation the simulation can be run with the following command::

    ~# gsy-e run

There are various options available to control the simulation run.
Help on there is available via::

    ~# gsy-e run --help


Controlling the simulation
--------------------------

While running a simulation, the following keyboard commands are available:

=== =======
Key Command
=== =======
i   Show information about simulation
p   Pause simulation
q   Quit simulation
r   Reset and restart simulation
R   Start a Python REPL at the current simulation step
s   Save current state of simulation to file (see below for resuming)
=== =======

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

    ~# docker build -t gsy-e .


After building is complete you can run the image with::

    ~# docker run --rm -it gsy-e


Command line parameters can be given normally after the image name::

    ~# docker run --rm gsy-e --help
    ~# docker run --rm gsy-e run --help
    ~# docker run --rm gsy-e run --setup default_2a -t15s


There is also a handy script that deals with the building of the image and running the provided command::

    ~# ./run_d3a_on_docker.sh "$docker_command" $export_path


where you can provide the d3a_command and export path where the simulation results are stored.
For example::

    ~# ./run_d3a_on_docker.sh "gsy-e -l ERROR run --setup default_2a -t 15s" $HOME/gsy-e-simulation


builds a gsy-e docker image (if not already present),
runs the simulation with setup-file default_2a, tick-length 15s
and stores the simulation output data into $HOME/gsy-e-simulation.
If no export_path is provided, simulation results will be stored in $HOME/gsy-e-simulation.


_`docker`: https://docker.io


Detailed Documentation
===============
Please refer to: https://gridsingularity.github.io/d3a/d3a-documentation/
