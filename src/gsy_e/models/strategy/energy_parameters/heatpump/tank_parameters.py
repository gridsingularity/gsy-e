from enum import Enum
from dataclasses import dataclass

from gsy_framework.constants_limits import ConstSettings


class HeatpumpTankTypes(Enum):
    """Supported types of heat tanks"""

    WATER = 0
    PCM = 1


class PCMType(Enum):
    """Type if PCM material"""

    OM37 = 1
    OM42 = 2
    OM46 = 3
    OM65 = 4


@dataclass
class TankParameters:
    # pylint: disable=too-many-instance-attributes)
    """Nameplate parameters of a heat tank."""
    # todo: create class just for PCM tanks and just for water tanks

    min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C
    tank_volume_L: float = ConstSettings.HeatPumpSettings.TANK_VOL_L
    type: HeatpumpTankTypes = HeatpumpTankTypes.WATER
    max_capacity_kJ: float = 6.0 * 3600
    name: str = ""
    pcm_tank_type: PCMType = PCMType.OM37
    mass_flow_rate: float = 10  # l/min
    number_of_plates: int = 15
