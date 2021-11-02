import platform

from setuptools import find_packages, setup

gsy_framework_branch = "feature/D3ASIM-3669"

try:
    with open("requirements/dev.txt") as req:
        REQUIREMENTS = [r.partition("#")[0] for r in req if not r.startswith("-e")]
        REQUIREMENTS.extend(
            [f"gsy-framework @ "
             f"git+https://github.com/faizan2590/gsy-framework.git@{gsy_framework_branch}"
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
    name="gsy-e",
    description="decentralised energy exchange developed by Grid Singularity",
    long_description=README,
    author="GridSingularity",
    author_email="d3a@gridsingularity.com",
    url="https://github.com/faizan2590/gsy-e",
    version=VERSION,
    packages=find_packages(where="src", exclude=["tests"]),
    package_dir={"": "src"},
    package_data={"d3a": ["resources/*.csv"]},
    install_requires=REQUIREMENTS,
    entry_points={
        "console_scripts": [
            "d3a = d3a.d3a_core.cli:main",
        ]
    },
    zip_safe=False,
)
