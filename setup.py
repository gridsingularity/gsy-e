import os
from setuptools import find_packages, setup

gsy_framework_branch = os.environ.get("GSY_FRAMEWORK_BRANCH", "master")
scm_engine_branch = os.environ.get("SCM_ENGINE_BRANCH")
scm_engine_repo = os.environ.get(
    "SCM_ENGINE_REPO", "git+ssh://git@github.com/gridsingularity/scm-engine.git"
)

try:
    with open("requirements/dev.txt", encoding="utf-8") as req:
        REQUIREMENTS = [r.partition("#")[0] for r in req if not r.startswith("-e")]
        REQUIREMENTS.extend(
            [
                f"gsy-framework @ "
                f"git+https://github.com/gridsingularity/gsy-framework.git@{gsy_framework_branch}"
            ]
        )
        if scm_engine_branch and scm_engine_repo:
            REQUIREMENTS.extend([f"scm-engine @ {scm_engine_repo}@{scm_engine_branch}"])
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
    entry_points={
        "console_scripts": [
            "gsy-e = gsy_e.gsy_e_core.cli:main",
            "d3a = gsy_e.gsy_e_core.cli:main",
        ]
    },
    zip_safe=False,
)
