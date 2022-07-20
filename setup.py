import platform

from setuptools import find_packages, setup

gsy_framework_branch = "master"

try:
    with open("requirements/blockchain.txt", encoding="utf-8") as req:
        REQUIREMENTS_BC = [r.partition("#")[0] for r in req if not r.startswith("-e")]
    with open("requirements/base.in", encoding="utf-8") as req:
        REQUIREMENTS = [r.partition("#")[0] for r in req if not r.startswith("-e")]
except OSError:
    # Shouldn't happen
    REQUIREMENTS = []

with open("README.rst", "r", encoding="utf-8") as readme:
    README = readme.read()

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
VERSION = "1.3.0"

setup(
    name="gsy-e",
    description="decentralised energy exchange developed by Grid Singularity",
    long_description=README,
    author="GridSingularity",
    author_email="contact@gridsingularity.com",
    url="https://github.com/gridsingularity/gsy-e",
    version=VERSION,
    packages=find_packages(where="src", exclude=["tests"]),
    package_dir={"": "src"},
    package_data={"gsy_e": ["resources/*.csv", "setup/gsy_e_settings.json"]},
    install_requires=REQUIREMENTS,
    extras_require = { 'bc': REQUIREMENTS_BC},
    entry_points={
        "console_scripts": [
            "gsy-e = gsy_e.gsy_e_core.cli:main"
        ]
    },
)
