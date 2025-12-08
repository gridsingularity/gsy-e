from enum import Enum
from dataclasses import dataclass
from pendulum import duration

from gsy_framework.constants_limits import ConstSettings, GlobalConfig


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
class BaseTankParameters:
    # pylint: disable=too-many-instance-attributes)
    """Base class for tank parameters"""

    type: HeatpumpTankTypes = HeatpumpTankTypes.WATER
    name: str = ""
    initial_temp_C: float = ConstSettings.HeatPumpSettings.INIT_TEMP_C
    loss_per_day_percent: float = ConstSettings.HeatPumpSettings.TANK_LOSS_PERCENT_DAY

    @property
    def per_market_slot_loss(self):
        """Return the loss per market slot."""
        return (self.loss_per_day_percent / (duration(hours=24) / GlobalConfig.slot_length)) / 100


@dataclass
class WaterTankParameters(BaseTankParameters):
    # pylint: disable=too-many-instance-attributes)
    """Nameplate parameters of a water tank."""

    min_temp_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    tank_volume_L: float = ConstSettings.HeatPumpSettings.TANK_VOL_L


@dataclass
class PCMTankParameters(BaseTankParameters):
    # pylint: disable=too-many-instance-attributes)
    """Nameplate parameters of a pcm tank."""

    min_temp_htf_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_htf_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    min_temp_pcm_C: float = ConstSettings.HeatPumpSettings.MIN_TEMP_C
    max_temp_pcm_C: float = ConstSettings.HeatPumpSettings.MAX_TEMP_C
    pcm_tank_type: PCMType = PCMType.OM37
    volume_flow_rate_l_min: float = 10
    number_of_plates: int = 15
