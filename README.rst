====================================
Grid Singularity Energy Exchange
====================================

.. image:: https://codecov.io/gh/gridsingularity/gsy-e/branch/master/graph/badge.svg?token=XTWK3DAKUA
   :target: https://codecov.io/gh/gridsingularity/gsy-e

The Grid Singularity Energy Exchange Engine is developed by `Grid Singularity <https://gridsingularity.com/>`__ as an interface (`Singularity Map <https://map.gridsingularity.com/singularity-map>`__) and open source codebase (see `Licensing <https://gridsingularity.github.io/d3a/licensing/>`__ to model, simulate, optimize and (coming soon) download and deploy interconnected, grid-aware energy marketplaces.
Grid Singularity has been proclaimed the `World Tech Pioneer by the World Economic Forum <https://www.weforum.org/organizations/grid-singularity-gmbh-gsy-gmbh>`__ and is also known as a co-founder of the `Energy Web Foundation <https://www.energyweb.org/>`__ that gathers leading energy corporations globally co-developing a shared blockchain-based platform.

Code of Conduct
===============
Please refer to: https://github.com/gridsingularity/gsy-e/blob/master/CODE_OF_CONDUCT.md

How to contribute:
==================
Please refer to: https://github.com/gridsingularity/gsy-e/blob/master/CONTRIBUTING.md


Basic setup
===========

(For instructions using `Docker`_ see below)

Clone the Repository

.. code-block::

   git clone --recurse-submodules https://github.com/BC4P/gsy-e/

After cloning this project setup a Python 3.10 virtualenv or conda env and install gsy-e using pip:
    
.. code-block::
    
    conda create -n bc4p python=3.10
    conda activate bc4p
    pip install -e . -e gsy-framework -e energyMarket

Unfortunatley, fixing versions through `pip-compile` from `pip-tools` does make things worse, as e.g. eth-brownie has other fixed versions, as gsy-framework, resulting in an unresolvable situation.
Install with pip only helps here, as it ignores those hard fixed versions.


The Simulation
==============

Running the simulation
----------------------

After installation the simulation can be run with the following command::

    ~# gsy-e run

There are various options available to control the simulation run.
Help on there is available via::

    ~# gsy-e run --help
    
To run the BC4P simulation use:
    
.. code-block::
    
    gsy-e run --setup bc4p.demonstration --enable-bc


This would start the simulation with the integrated ganache-cli and blockchain integration - which does not work yet.

One can let the simulation run in real-time by setting the slot-length-realtime to the same intervall as the slot-length `-s`.
To allow the integration of other workers through the redis connection, one can use `--enable-external-connection`

.. code-block::
    
    gsy-e run --setup bc4p.demonstration -t 30s -s 15m --enable-external-connection --start-date 2022-07-01

Controlling the simulation
--------------------------

This is not available on Windows.

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


InfluxDb Configuration
===========
Edit following config file example:
.. code-block::
    src/gsy_e/gsy-framework/gsy-framework/influx_connection/resources/influxdb.cfg.example

1. edit password and username of InfluxDB (and or change the other settings, if another InfluxDB should be used)
2. save as new file with name "influxdb.cfg" (This file will not be tracked in git)


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
======================
Please refer to: https://gridsingularity.github.io/gsy-e/documentation/
