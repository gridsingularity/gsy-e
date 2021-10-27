import platform

from setuptools import find_packages, setup

d3a_interface_branch = "master"

try:
    with open("requirements/dev.txt") as req:
        REQUIREMENTS = [r.partition("#")[0] for r in req if not r.startswith("-e")]
        REQUIREMENTS.extend(
            [f"d3a-interface @ "
             f"git+https://github.com/gridsingularity/d3a-interface.git@{d3a_interface_branch}"
             ])
except OSError:
    # Shouldn't happen
    REQUIREMENTS = []

with open("README.rst", "r") as readme:
    README = readme.read()

if platform.python_implementation() == "PyPy":
    REQUIREMENTS.append("psycopg2cffi==2.9.0")
else:
    REQUIREMENTS.append("psycopg2==2.9.1")

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
VERSION = "1.1.0"

setup(
    name="d3a",
    description="decentralised energy exchange developed by Grid Singularity",
    long_description=README,
    author="GridSingularity",
    author_email="d3a@gridsingularity.com",
    url="https://github.com/gridsingularity/d3a",
    version=VERSION,
    packages=find_packages(where="src", exclude=["tests"]),
    package_dir={"": "src"},
    package_data={"d3a": ["resources/*.csv"]},
    install_requires=REQUIREMENTS,
    entry_points={
        "console_scripts": [
            "d3a = d3a.gsy_core.cli:main",
        ]
    },
    zip_safe=False,
)
