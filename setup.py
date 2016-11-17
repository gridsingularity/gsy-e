from setuptools import setup, find_packages


try:
    with open('requirements/base.txt') as req:
        REQUIREMENTS = [r.partition('#')[0] for r in req if not r.startswith('-e')]
except OSError:
    # Shouldn't happen
    REQUIREMENTS = []

with open("README.rst", "r") as readme:
    README = readme.read()

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
VERSION = '1.0.0a0'

setup(
    name="d3a",
    description="GridSingularity AreaManager PoC",
    long_description=README,
    author='GridSingularity',
    author_email='info@gridsingularity.com',
    url='https://github.com/gridsingularity/d3a',
    version=VERSION,
    packages=find_packages(where="src", exclude=["tests"]),
    package_dir={"": "src"},
    install_requires=REQUIREMENTS,
    entry_points={
        'console_scripts': [
            'd3a = d3a.cli:main',
        ]
    },
    zip_safe=False,
)
