from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import ConstSettings


'''
In this test file one storage with high demand is used, in order to enforce the bid that
it will place to be tokenized into smaller bids. The supply is provided by 5 PVs
with one solar panel on each, in order to not cover the storage demand by one offer, but to
partially cover the demand with each different offer.
Expected result: when having set the log level to WARN, there should be 5 distinct trade chains
on each market slot (on market slots that PVs can provide energy though). These trades should
be a chain of bid and offer trades from the PVs to the storage. For simplicity, the iaa_fee is set
to 0, and all the offer/bid trades should have the same energy rate (about 15 ct/kWh, depending
on the interpolation of bids and offers).
'''


def get_setup(config):
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2
    ConstSettings.MIN_PV_SELLING_RATE = 0
    ConstSettings.DEFAULT_MARKET_MAKER_RATE = 30
    ConstSettings.STORAGE_MIN_BUYING_RATE = 0
    ConstSettings.STORAGE_BREAK_EVEN_BUY = 29.9
    ConstSettings.STORAGE_BREAK_EVEN_SELL = 30

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage',
                         strategy=StorageStrategy(initial_capacity=1.1,
                                                  battery_capacity=10,
                                                  max_abs_battery_power=5,
                                                  break_even=(
                                                      ConstSettings.STORAGE_BREAK_EVEN_BUY,
                                                      ConstSettings.STORAGE_BREAK_EVEN_SELL)
                                                  ),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV1',
                         strategy=PVStrategy(1, 0),
                         appliance=PVAppliance()
                         ),
                    Area('H2 PV2',
                         strategy=PVStrategy(1, 0),
                         appliance=PVAppliance()
                         ),
                    Area('H2 PV3',
                         strategy=PVStrategy(1, 0),
                         appliance=PVAppliance()
                         ),
                    Area('H2 PV4',
                         strategy=PVStrategy(1, 0),
                         appliance=PVAppliance()
                         ),
                    Area('H2 PV5',
                         strategy=PVStrategy(1, 0),
                         appliance=PVAppliance()
                         ),
                ]
            ),
        ],
        config=config
    )
    return area
