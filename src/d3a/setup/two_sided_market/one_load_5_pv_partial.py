from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import ConstSettings


'''
In this test file one load with high demand is used, in order to enforce the bid that
it will place to be tokenized into smaller bids. The supply is provided by 5 PVs
with one solar panel on each, in order to not cover the load by one offer, but to
partially cover the demand with each different offer.
Expected result: when having set the log level to WARN, there should be 5 distinct trade chains
on each market slot (on market slots that PVs can provide energy though). These trades should
be a chain of bid and offer trades from the PVs to the load. For simplicity, the iaa_fee is set
to 0 (it has to be set via the CLI, by configuring the cli argument iaa_fee to 0), and all the
offer/bid trades should have the same energy rate (about 15 ct/kWh, depending on the
interpolation of bids and offers).
'''


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.PVSettings.MIN_SELLING_RATE = 0
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 30
    ConstSettings.LoadSettings.MIN_ENERGY_RATE = 0
    ConstSettings.LoadSettings.MAX_ENERGY_RATE = 30

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(
                        avg_power_W=1000,
                        hrs_per_day=24,
                        hrs_of_day=list(range(0, 24)),
                        min_energy_rate=ConstSettings.LoadSettings.MIN_ENERGY_RATE,
                        max_energy_rate=ConstSettings.LoadSettings.MAX_ENERGY_RATE
                    ), appliance=SwitchableAppliance()),
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
