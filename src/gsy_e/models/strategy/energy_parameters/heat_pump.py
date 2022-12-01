from typing import Dict, TYPE_CHECKING

from gsy_framework.constants_limits import ConstSettings
from pendulum import DateTime

from gsy_e.models.state import HeatPumpState

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase


class HeatPumpEnergyParameters:
    """Energy Parameters for the heat pump."""
    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(self,
                 maximum_power_rating: float = ConstSettings.HeatPumpSettings.MAX_POWER_RATING_KW,
                 min_temperatur_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C,
                 max_temperatur_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C,
                 external_temperatur_C: float = ConstSettings.HeatPumpSettings.EXT_TEMP_C,
                 tank_volume_l: float = ConstSettings.HeatPumpSettings.TANK_VOL_L,
                 average_consumption: float =
                 ConstSettings.HeatPumpSettings.CONSUMPTION_KW,
                 source_type: int = ConstSettings.HeatPumpSettings.SOURCE_TYPE):

        self.maximum_power_rating = maximum_power_rating
        self.min_temperatur_C = min_temperatur_C
        self.max_temperatur_C = max_temperatur_C
        self.external_temperatur_C = external_temperatur_C
        self.tank_volume_l = tank_volume_l
        self.average_consumption = average_consumption
        self.source_type = source_type

        self.state = HeatPumpState()

        self.energy_loss_kWh: Dict[DateTime, float] = {}
        self.energy_demand_kWh: Dict[DateTime, float] = {}

    def get_energy_to_buy(self):
        """To be implemented in the frame of GSYE-426"""

    def serialize(self):
        """To be implemented in the frame of GSYE-426"""

    def event_traded_energy(self, market: "MarketBase", market_slot: DateTime):
        """To be implemented in the frame of GSYE-426"""

    def decrement_posted_energy(self, market: "MarketBase", market_slot: DateTime):
        """To be implemented in the frame of GSYE-426"""
