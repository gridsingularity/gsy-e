"""
Creates a WindStrategy that uses a profile as input for its power values.
"""
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy


class WindUserProfileStrategy(PVUserProfileStrategy):
    parameters = ('power_profile', 'risk', 'panel_count')

    def __init__(self, power_profile, risk: int=ConstSettings.GeneralSettings.DEFAULT_RISK,
                 min_selling_rate: float=ConstSettings.PVSettings.MIN_SELLING_RATE,
                 initial_rate_option: int=ConstSettings.PVSettings.INITIAL_RATE_OPTION,
                 energy_rate_decrease_option=ConstSettings.PVSettings.RATE_DECREASE_OPTION,
                 energy_rate_decrease_per_update=ConstSettings.GeneralSettings.
                 ENERGY_RATE_DECREASE_PER_UPDATE
                 ):
        super().__init__(power_profile=power_profile, risk=risk, min_selling_rate=min_selling_rate,
                         initial_rate_option=initial_rate_option,
                         energy_rate_decrease_option=energy_rate_decrease_option,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update
                         )
