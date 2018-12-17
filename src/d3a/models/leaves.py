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
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant


class Leaf(Area):
    """
    Superclass for frequently used leaf Areas, so they can be
    instantiated and serialized in a more compact format
    """
    strategy_type = None
    appliance_type = SimpleAppliance

    def __init__(self, name, config=None, **kwargs):
        super(Leaf, self).__init__(
            name=name,
            strategy=self.strategy_type(**{
                key: value for key, value in kwargs.items()
                if key in (self.strategy_type.parameters or []) and value is not None
            }),
            appliance=self.appliance_type(),
            config=config
        )

    @property
    def parameters(self):
        return {key: getattr(self.strategy, key, None)
                for key in self.strategy_type.parameters}


class CommercialProducer(Leaf):
    strategy_type = CommercialStrategy


class PV(Leaf):
    strategy_type = PVStrategy
    appliance_type = PVAppliance


class PredefinedPV(Leaf):
    strategy_type = PVPredefinedStrategy
    appliance_type = PVAppliance


class PVProfile(Leaf):
    strategy_type = PVUserProfileStrategy
    appliance_type = PVAppliance


class LoadProfile(Leaf):
    strategy_type = DefinedLoadStrategy
    appliance_type = SwitchableAppliance


class Storage(Leaf):
    strategy_type = StorageStrategy
    appliance_type = SwitchableAppliance


class LoadHours(Leaf):
    strategy_type = LoadHoursStrategy
    appliance_type = SwitchableAppliance


class CellTower(Leaf):
    strategy_type = CellTowerLoadHoursStrategy
    appliance_type = SwitchableAppliance


class FiniteDieselGenerator(Leaf):
    strategy_type = FinitePowerPlant
    appliance_type = SwitchableAppliance


class Light(Leaf):
    strategy_type = LoadHoursStrategy
    appliance_type = SwitchableAppliance


class TV(Leaf):
    strategy_type = LoadHoursStrategy
    appliance_type = SwitchableAppliance
