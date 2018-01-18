from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.const import DEFAULT_RISK
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.pv import PVStrategy


class ModifiedFridgeStrategy(FridgeStrategy):
    def __init__(self, risk=DEFAULT_RISK):
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
                Area('H2 Fridge', strategy=ModifiedFridgeStrategy(), appliance=FridgeAppliance())
            ]),
            Area(
                'Commercial Energy Producer',
                strategy=CommercialStrategy(energy_range_wh=(5, 10), energy_price=30),
                appliance=SimpleAppliance()
            )
        ],
        config=config
    )
    return area
