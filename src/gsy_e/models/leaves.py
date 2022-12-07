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

from gsy_e.models.area import Area, CoefficientArea
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.external_strategies.load import (
    LoadHoursForecastExternalStrategy, LoadProfileForecastExternalStrategy,
    LoadHoursExternalStrategy, LoadProfileExternalStrategy)
from gsy_e.models.strategy.external_strategies.pv import (PVExternalStrategy,
                                                          PVForecastExternalStrategy,
                                                          PVPredefinedExternalStrategy,
                                                          PVUserProfileExternalStrategy)
from gsy_e.models.strategy.external_strategies.smart_meter import SmartMeterExternalStrategy
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy, SCMLoadProfileStrategy
from gsy_e.models.strategy.scm.pv import SCMPVPredefinedStrategy, SCMPVStrategy, SCMPVUserProfile
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.predefined_wind import WindUserProfileStrategy
from gsy_e.models.strategy.forward.pv import ForwardPVStrategy
from gsy_e.models.strategy.forward.load import ForwardLoadStrategy
from gsy_e.models.strategy.scm.external.pv import ExternalSCMPVStrategy
from gsy_e.models.strategy.scm.external.load import ExternalSCMLoadHoursStrategy

external_strategies_mapping = {
    LoadHoursStrategy: LoadHoursExternalStrategy,
    DefinedLoadStrategy: LoadProfileExternalStrategy,
    PVStrategy: PVExternalStrategy,
    PVPredefinedStrategy: PVPredefinedExternalStrategy,
    PVUserProfileStrategy: PVUserProfileExternalStrategy,
    StorageStrategy: StorageExternalStrategy,
    SmartMeterStrategy: SmartMeterExternalStrategy
}

forecast_strategy_mapping = {
    PVPredefinedStrategy: PVForecastExternalStrategy,
    PVStrategy: PVForecastExternalStrategy,
    PVUserProfileStrategy: PVForecastExternalStrategy,
    DefinedLoadStrategy: LoadProfileForecastExternalStrategy,
    LoadHoursStrategy: LoadHoursForecastExternalStrategy
}


class LeafBase:
    """
    Superclass for frequently used leaf Areas, so they can be
    instantiated and serialized in a more compact format
    """
    strategy_type = None
    strategy = None

    def __init__(self, name, config, uuid=None, **kwargs):
        if config.external_connection_enabled:
            if kwargs.get("forecast_stream_enabled", False) is True:
                try:
                    self.strategy_type = forecast_strategy_mapping[self.strategy_type]
                except KeyError:
                    logging.error("%s could not be found in forecast_strategy_mapping, "
                                  "using template strategy.", self.strategy_type)
            elif kwargs.get("allow_external_connection", False) is True:
                try:
                    self.strategy_type = external_strategies_mapping[self.strategy_type]
                except KeyError:
                    logging.error("%s could not be found in external_strategies_mapping, "
                                  "using template strategy.", self.strategy_type)

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
            logging.warning("Trying to construct area strategy %s with not allowed "
                            "arguments %s", name, not_accepted_args)
        try:
            super().__init__(
                name=name,
                strategy=self.strategy_type(**{
                    key: value for key, value in kwargs.items()
                    if key in allowed_arguments and value is not None
                }),
                config=config,
                uuid=uuid
            )
        except TypeError as ex:
            logging.error("Cannot create leaf area %s with strategy %s and parameters %s.",
                          name, self.strategy_type, kwargs)
            raise ex

    @property
    def parameters(self):
        """Get dict with the strategy parameters and their values."""
        return self.strategy.serialize()


# pylint: disable=missing-class-docstring


class Leaf(LeafBase, Area):
    pass


class CoefficientLeaf(LeafBase, CoefficientArea):
    pass


class CommercialProducer(Leaf):
    strategy_type = CommercialStrategy


class InfiniteBus(Leaf):
    strategy_type = InfiniteBusStrategy


class MarketMaker(Leaf):
    strategy_type = MarketMakerStrategy


class PV(Leaf):
    strategy_type = PVStrategy


class PredefinedPV(Leaf):
    strategy_type = PVPredefinedStrategy


class PVProfile(Leaf):
    strategy_type = PVUserProfileStrategy


class WindTurbine(Leaf):
    strategy_type = WindUserProfileStrategy


class LoadProfile(Leaf):
    strategy_type = DefinedLoadStrategy


class LoadHours(Leaf):
    strategy_type = LoadHoursStrategy


class Storage(Leaf):
    strategy_type = StorageStrategy


class SmartMeter(Leaf):
    strategy_type = SmartMeterStrategy


class ForwardLoad(Leaf):
    strategy_type = ForwardLoadStrategy


class ForwardPV(Leaf):
    strategy_type = ForwardPVStrategy


class FiniteDieselGenerator(Leaf):
    strategy_type = FinitePowerPlant


class SCMPV(CoefficientLeaf):
    strategy_type = SCMPVStrategy


class SCMPredefinedPV(CoefficientLeaf):
    strategy_type = SCMPVPredefinedStrategy


class SCMPVProfile(CoefficientLeaf):
    strategy_type = SCMPVUserProfile


class SCMLoadProfile(CoefficientLeaf):
    strategy_type = SCMLoadProfileStrategy


class SCMLoadHours(CoefficientLeaf):
    strategy_type = SCMLoadHoursStrategy


class SCMStorage(CoefficientLeaf):
    strategy_type = SCMStorageStrategy


scm_leaf_mapping = {
    "LoadHours": SCMLoadHours,
    "LoadProfile": SCMLoadProfile,
    "Storage": SCMStorage,
    "PV": SCMPV,
    "PredefinedPV": SCMPredefinedPV,
    "PVProfile": SCMPVProfile
}

external_scm_leaf_mapping = {
    "LoadHours": ExternalSCMLoadHoursStrategy,
    "LoadProfile": ExternalSCMLoadHoursStrategy,
    "PV": ExternalSCMPVStrategy,
    "PredefinedPV": ExternalSCMPVStrategy,
    "PVProfile": ExternalSCMPVStrategy
}

forward_leaf_mapping = {
    "LoadHours": ForwardLoad,
    "PV": ForwardPV
}
