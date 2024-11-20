"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import inspect
import logging

from scm.coefficient_area import CoefficientArea
from scm.strategies.heat_pump import ScmHeatPumpStrategy
from scm.strategies.load import SCMLoadHoursStrategy, SCMLoadProfileStrategy
from scm.strategies.pv import SCMPVUserProfile
from scm.strategies.storage import SCMStorageStrategy


class LeafBase:
    """
    Superclass for frequently used leaf Areas, so they can be
    instantiated and serialized in a more compact format
    """

    strategy_type = None
    strategy = None

    def __init__(self, name, config, uuid=None, **kwargs):
        # The following code is used in order to collect all the available constructor arguments
        # from the strategy class that needs to be constructed, and cross-check with the input
        # arguments (kwargs) in order to verify that all arguments are valid for the strategy,
        # and to log a warning and omit them if they are not valid for the strategy.
        # This approach traverses over the class hierarchy in order to fetch all constructor
        # arguments from all base classes. The reason why this is needed, is because some derived
        # classes (e.g. all the external strategies) do not define a constructor, thus using the
        # default one (def __init__(self, *args, **kwargs)) and thus making it impossible to read
        # the constructor arguments.

        # Gather all constructor arguments from all base classes of the strategy class.
        allowed_arguments = ["self"]
        for strategy_base in self.strategy_type.__mro__:
            if "__init__" in strategy_base.__dict__:
                allowed_arguments += inspect.getfullargspec(strategy_base).args[1:]

        # Filter out the arguments that are not accepted by any constructor in the strategy
        # class hierarchy and log them.
        not_accepted_args = set(kwargs.keys()).difference(allowed_arguments)
        if not_accepted_args:
            logging.warning(
                "Trying to construct area strategy %s with not allowed " "arguments %s",
                name,
                not_accepted_args,
            )
        try:
            super().__init__(
                name=name,
                strategy=self.strategy_type(
                    **{
                        key: value
                        for key, value in kwargs.items()
                        if key in allowed_arguments and value is not None
                    }
                ),
                config=config,
                uuid=uuid,
            )
        except TypeError as ex:
            logging.error(
                "Cannot create leaf area %s with strategy %s and parameters %s.",
                name,
                self.strategy_type,
                kwargs,
            )
            raise ex

    @property
    def parameters(self):
        """Get dict with the strategy parameters and their values."""
        return self.strategy.serialize()


# pylint: disable=missing-class-docstring
class CoefficientLeaf(LeafBase, CoefficientArea):
    pass


class SCMPVProfile(CoefficientLeaf):
    strategy_type = SCMPVUserProfile


class SCMLoadProfile(CoefficientLeaf):
    strategy_type = SCMLoadProfileStrategy


class SCMHeatPump(CoefficientLeaf):
    strategy_type = ScmHeatPumpStrategy


class SCMLoadHours(CoefficientLeaf):
    strategy_type = SCMLoadHoursStrategy


class SCMStorage(CoefficientLeaf):
    strategy_type = SCMStorageStrategy


scm_leaf_mapping = {
    "LoadHours": SCMLoadHours,
    "LoadProfile": SCMLoadProfile,
    "ScmStorage": SCMStorage,
    "PV": SCMPVProfile,
    "PVProfile": SCMPVProfile,
    "ScmHeatPump": SCMHeatPump,
}
