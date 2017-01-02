from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.simple import OfferStrategy
from d3a.models.strategy.storage import StorageStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 PV', strategy=PVStrategy(), appliance=SimpleAppliance()),
                    Area('H1 Fridge', strategy=FridgeStrategy(), appliance=SimpleAppliance()),
                    Area('H1 Storage', strategy=StorageStrategy(), appliance=SimpleAppliance())
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV', strategy=PVStrategy(), appliance=SimpleAppliance()),
                    Area('H2 Fridge', strategy=FridgeStrategy(), appliance=SimpleAppliance()),
                    Area('H2 Storage', strategy=StorageStrategy(), appliance=SimpleAppliance())
                ]
            ),
            Area('Hydro', strategy=OfferStrategy(offer_chance=.1,
                                                 price_fraction_choice=(0.03, 0.05)))
        ],
        config=config
    )
    return area
