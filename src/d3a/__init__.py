# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
import os
import d3a
VERSION = "1.0.0a0"


def get_project_root():
    return os.path.dirname(d3a.__file__)


def get_contract_path(contract_name):
    contract_path = os.path.join(
        get_project_root(),
        'contracts',
        contract_name
    )
    return os.path.realpath(contract_path)
