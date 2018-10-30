from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.e_car import ECarStrategy
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.deprecated.greedy_night_storage import NightStorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy


class ModifiedFridgeStrategy(FridgeStrategy):
    def __init__(self, risk=ConstSettings.GeneralSettings.DEFAULT_RISK):
        self.accept_count = 0
        super().__init__(risk)

    # buy partial offers sometimes
    def accept_offer(self, market, offer, *, buyer=None, energy=None):
        self.accept_count += 1
        if self.accept_count % 9 == 0:
            energy = 0.9 * (energy or offer.energy)
            self.log.error("PARTIAL OFFER")
        super(ModifiedFridgeStrategy, self).accept_offer(
            market, offer, buyer=buyer, energy=energy
        )


def get_setup(config):
    area = Area(
        'Grid', [
            Area('House 1', [
                Area('H1 PV', strategy=PVStrategy(2, 40), appliance=PVAppliance()),
                Area('H1 Fridge', strategy=ModifiedFridgeStrategy(), appliance=FridgeAppliance())
            ]),
            Area('House 2', [
                Area('H2 Storage',
                     strategy=StorageStrategy(initial_capacity_kWh=5.0),
                     appliance=SimpleAppliance()),
                Area('H2 ECar', strategy=ECarStrategy(), appliance=SimpleAppliance()),
                Area('H2 Fridge', strategy=ModifiedFridgeStrategy(), appliance=FridgeAppliance())
            ]),
            Area('House 3', [
                Area('H3 NightStorage',
                     strategy=NightStorageStrategy(),
                     appliance=SimpleAppliance()),
                Area('H3 Fridge 1',
                     strategy=ModifiedFridgeStrategy(),
                     appliance=FridgeAppliance()),
                Area('H3 Fridge 2',
                     strategy=ModifiedFridgeStrategy(),
                     appliance=FridgeAppliance()),
                Area('H3 Charger',
                     strategy=LoadHoursStrategy(avg_power_W=10,
                                                hrs_per_day=4,
                                                hrs_of_day=list(range(8, 22))),
                     appliance=SimpleAppliance())
            ]),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30),
                 appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
