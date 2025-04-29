from enum import Enum
from dataclasses import dataclass

from gsy_framework.constants_limits import ConstSettings


class HeatpumpTankTypes(Enum):
    """Supported types of heat tanks"""

    WATER = 0
    PCM = 1


@dataclass
class TankParameters:
    """Nameplate parameters of a heat tank."""

    min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C
    tank_volume_L: float = ConstSettings.HeatPumpSettings.TANK_VOL_L
    type: HeatpumpTankTypes = HeatpumpTankTypes.WATER
    max_capacity_kJ: float = 6.0 * 3600
