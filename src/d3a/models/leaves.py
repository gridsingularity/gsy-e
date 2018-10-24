from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.e_car import ECarStrategy
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.permanent import PermanentLoadStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.heatpump import HeatPumpStrategy
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


class ECar(Leaf):
    strategy_type = ECarStrategy


class Fridge(Leaf):
    strategy_type = FridgeStrategy
    appliance_type = FridgeAppliance


class PermanentLoad(Leaf):
    strategy_type = PermanentLoadStrategy


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


class Heatpump(Leaf):
    strategy_type = HeatPumpStrategy


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
