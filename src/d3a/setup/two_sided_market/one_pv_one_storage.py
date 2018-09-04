from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import ConstSettings


def get_setup(config):
    # Two sided market
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
                         strategy=StorageStrategy(initial_capacity=0.6,
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
                    Area('H2 PV',
                         strategy=PVStrategy(4, 0),
                         appliance=PVAppliance()
                         ),

                ]
            ),
        ],
        config=config
    )
    return area
