from gsy_e.models.area import Area
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import BidOfferMatchAlgoEnum


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = \
        BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value
    area = Area(
            name="GRID",
            children=[
                    Area(
                            name="Building-1",
                            children=[
                                    Area(
                                            name="Office1X",
                                            children=[
                                                    Area(
                                                            name="Office1X-PV",
                                                            strategy=PVStrategy(
                                                                    panel_count=50,
                                                                    capacity_kW=0.2,
                                                                    initial_selling_rate=25,
                                                                    final_selling_rate=15)
                                                            ),
                                                    Area(
                                                            name="Office1X-LOAD",
                                                            strategy=LoadHoursStrategy(
                                                                    avg_power_W=500,
                                                                    hrs_of_day=[7, 8, 17, 18, 19],
                                                                    initial_buying_rate=0,
                                                                    final_buying_rate=26)
                                                            )
                                                    ],
                                            ),
                                    Area(
                                            name="Office1Y",
                                            children=[
                                                    Area(
                                                            name="Office1Y-LOAD",
                                                            strategy=LoadHoursStrategy(
                                                                    avg_power_W=1000,
                                                                    hrs_of_day=list(range(24)),
                                                                    initial_buying_rate=0,
                                                                    final_buying_rate=29)
                                                            )
                                                    ]
                                            )
                                            ],
                                            ),
                    Area(
                            name="Building-2",
                            children=[
                                    Area(
                                            name="Office2X",
                                            children=[
                                                    Area(
                                                            name="Office2X-PV",
                                                            strategy=PVStrategy(
                                                                    panel_count=50,
                                                                    capacity_kW=0.2,
                                                                    initial_selling_rate=25,
                                                                    final_selling_rate=5)
                                                            ),
                                                    Area(
                                                            name="Office2X-LOAD",
                                                            strategy=LoadHoursStrategy(
                                                                    avg_power_W=500,
                                                                    hrs_of_day=[7, 8, 17, 18, 19],
                                                                    initial_buying_rate=0,
                                                                    final_buying_rate=29)
                                                            )
                                                    ],
                                            ),
                                    Area(
                                            name="Office2Y",
                                            children=[
                                                    Area(
                                                            name="Office2Y-LOAD",
                                                            strategy=LoadHoursStrategy(
                                                                    avg_power_W=1000,
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
