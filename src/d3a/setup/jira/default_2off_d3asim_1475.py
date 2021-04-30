from d3a.models.area import Area
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = 2
    area = Area(
            name='GRID',
            children=[
                    Area(
                            name='Building-1',
                            children=[
                                    Area(
                                            name='Office1X',
                                            children=[
                                                    Area(
                                                            name='Office1X-PV',
                                                            strategy=PVStrategy(
                                                                    panel_count=50,
                                                                    max_panel_power_W=200,
                                                                    initial_selling_rate=25,
                                                                    final_selling_rate=15)
                                                            ),
                                                    Area(
                                                            name='Office1X-LOAD',
                                                            strategy=LoadHoursStrategy(
                                                                    avg_power_W=500,
                                                                    hrs_per_day=5,
                                                                    hrs_of_day=[7, 8, 17, 18, 19],
                                                                    initial_buying_rate=0,
                                                                    final_buying_rate=26)
                                                            )
                                                    ],
                                            ),
                                    Area(
                                            name='Office1Y',
                                            children=[
                                                    Area(
                                                            name='Office1Y-LOAD',
                                                            strategy=LoadHoursStrategy(
                                                                    avg_power_W=1000,
                                                                    hrs_per_day=24,
                                                                    hrs_of_day=list(range(24)),
                                                                    initial_buying_rate=0,
                                                                    final_buying_rate=29)
                                                            )
                                                    ]
                                            )
                                            ],
                                            ),
                    Area(
                            name='Building-2',
                            children=[
                                    Area(
                                            name='Office2X',
                                            children=[
                                                    Area(
                                                            name='Office2X-PV',
                                                            strategy=PVStrategy(
                                                                    panel_count=50,
                                                                    max_panel_power_W=200,
                                                                    initial_selling_rate=25,
                                                                    final_selling_rate=5)
                                                            ),
                                                    Area(
                                                            name='Office2X-LOAD',
                                                            strategy=LoadHoursStrategy(
                                                                    avg_power_W=500,
                                                                    hrs_per_day=5,
                                                                    hrs_of_day=[7, 8, 17, 18, 19],
                                                                    initial_buying_rate=0,
                                                                    final_buying_rate=29)
                                                            )
                                                    ],
                                            ),
                                    Area(
                                            name='Office2Y',
                                            children=[
                                                    Area(
                                                            name='Office2Y-LOAD',
                                                            strategy=LoadHoursStrategy(
                                                                    avg_power_W=1000,
                                                                    hrs_per_day=24,
                                                                    hrs_of_day=list(range(24)),
                                                                    initial_buying_rate=0,
                                                                    final_buying_rate=20)
                                                            )
                                                    ]
                                            )
                                            ],
                                            ),
                                            ],
            config=config
    )
    return area
