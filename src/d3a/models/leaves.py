"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy, \
    LoadProfileExternalStrategy, LoadForecastExternalStrategy
from d3a.models.strategy.external_strategies.pv import PVExternalStrategy, \
    PVPredefinedExternalStrategy, PVUserProfileExternalStrategy, PVForecastExternalStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy

external_strategies_mapping = {
    LoadHoursStrategy: LoadHoursExternalStrategy,
    DefinedLoadStrategy: LoadProfileExternalStrategy,
    PVStrategy: PVExternalStrategy,
    PVPredefinedStrategy: PVPredefinedExternalStrategy,
    PVUserProfileStrategy: PVUserProfileExternalStrategy,
    StorageStrategy: StorageExternalStrategy
}

forecast_strategy_mapping = {
    PVPredefinedStrategy: PVForecastExternalStrategy,
    PVStrategy: PVForecastExternalStrategy,
    PVUserProfileStrategy: PVForecastExternalStrategy,
    DefinedLoadStrategy: LoadForecastExternalStrategy,
    LoadHoursStrategy: LoadForecastExternalStrategy
}


class Leaf(Area):
    """
    Superclass for frequently used leaf Areas, so they can be
    instantiated and serialized in a more compact format
    """
    strategy_type = None

    def __init__(self, name, config=None, uuid=None, **kwargs):
        if kwargs.get("forecast_stream_enabled", False) is True:
            self.strategy_type = forecast_strategy_mapping[self.strategy_type]
        elif kwargs.get("allow_external_connection", False) is True:
            self.strategy_type = external_strategies_mapping[self.strategy_type]
        super(Leaf, self).__init__(
            name=name,
            strategy=self.strategy_type(**{
                key: value for key, value in kwargs.items()
                if key in (self.strategy_type.parameters or []) and value is not None
            }),
            config=config,
            uuid=uuid
        )

    @property
    def parameters(self):
        return {key: getattr(self.strategy, key, None)
                for key in self.strategy_type.parameters}


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


class LoadProfile(Leaf):
    strategy_type = DefinedLoadStrategy


class Storage(Leaf):
    strategy_type = StorageStrategy


class LoadHours(Leaf):
    strategy_type = LoadHoursStrategy


class FiniteDieselGenerator(Leaf):
    strategy_type = FinitePowerPlant


class Light(Leaf):
    strategy_type = LoadHoursStrategy


class TV(Leaf):
    strategy_type = LoadHoursStrategy
