"""
Setup for a microgrid + DSO


"""
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.appliance.simple import SimpleAppliance


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 1
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 5

    Houses_initial_buying_rate = 6
    Houses_final_buying_rate = 30

    area = Area(
        'Grid',
        [
            Area(
                'Microgrid',
                [
                    Area(
                        'House 1',
                        [
                            Area('H1 General Load', strategy=LoadHoursStrategy(
                                avg_power_W=100,
                                hrs_per_day=5, hrs_of_day=[9, 10, 11, 12, 13, 14, 15, 16],
                                initial_buying_rate=Houses_initial_buying_rate,
                                final_buying_rate=Houses_final_buying_rate),
                                 appliance=SwitchableAppliance()),

                            Area('H1 PV', strategy=PVStrategy(panel_count=3,
                                                              max_panel_power_W=250,  # to test
                                                              initial_selling_rate=30,
                                                              final_selling_rate=0),
                                 appliance=PVAppliance()),

                        ], transfer_fee_pct=0, transfer_fee_const=0,
                    ),


                    Area(
                        'House 2',
                        [
                            Area('H2 General Load', strategy=LoadHoursStrategy(
                                avg_power_W=100,
                                hrs_per_day=5, hrs_of_day=[9, 10, 11, 12, 13, 14, 15, 16],
                                initial_buying_rate=Houses_initial_buying_rate,
                                final_buying_rate=Houses_final_buying_rate),
                                 appliance=SwitchableAppliance()),

                            Area('H2 PV', strategy=PVStrategy(panel_count=4,
                                                              max_panel_power_W=250,
                                                              initial_selling_rate=30,
                                                              final_selling_rate=0),
                                 appliance=PVAppliance()),

                        ], transfer_fee_pct=0, transfer_fee_const=0,
                    ),
                ],),

            Area('DSO', strategy=InfiniteBusStrategy(energy_buy_rate=5),
                 appliance=SimpleAppliance()),

        ],
        config=config, transfer_fee_pct=0, transfer_fee_const=0,
    )
    return area
