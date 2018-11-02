from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.const import ConstSettings


def get_setup(config):
    ConstSettings.BlockchainSettings.START_LOCAL_CHAIN = False
    area = Area(
        'Grid',
        [
            Area('Cell Tower', strategy=LoadHoursStrategy(avg_power_W=25,
                                                          hrs_per_day=24),
                 appliance=SwitchableAppliance()),
            Area('Commercial Energy Producer',
                 strategy=FinitePowerPlant(energy_rate=30,
                                           max_available_power_kW=100),
                 appliance=SimpleAppliance()
                 ),

        ],
        config=config
    )
    return area
