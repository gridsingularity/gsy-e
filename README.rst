d3a: GridSingularity AreaManager PoC
====================================

Dev environment
---------------

After cloning this project setup a Python 3.5 virtualenv and install `pip-tools`_::

    ~# pip install pip-tools

To install the dependencies run the following command::

    ~# pip-sync requirements/*.txt



Updating requirements
---------------------

We use `pip-tools`_ to manage requirements.
To update the pinned requirements use the following command::

    ~# fab compile_reqs



_`pip-tools`: https://github.com/nvie/pip-tools
