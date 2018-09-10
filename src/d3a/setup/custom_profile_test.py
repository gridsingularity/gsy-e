from pendulum import duration

from d3a.models.appliance.custom_profile import CustomProfileAppliance
from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.area import Area
from d3a.models.strategy.custom_profile import custom_profile_strategy_from_list
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.pv import PVStrategy


values = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
          0.0, 0.4, 0.9, 1.5, 1.7, 1.7,
          0.1, 0.9, 1.1, 1.2, 0.5, 0.0,
          0.0, 0.4, 0.0, 0.0, 0.0, 0.0]

time_step = duration(hours=1)


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Custom', appliance=CustomProfileAppliance(),
                         strategy=custom_profile_strategy_from_list(consumption=values,
                                                                    time_step=time_step)),
                    Area('H1 PV', strategy=PVStrategy(), appliance=PVAppliance()),
                    Area('H1 Fridge', strategy=FridgeStrategy(), appliance=FridgeAppliance())
                ]
            )
        ],
        config=config
    )
    return area
