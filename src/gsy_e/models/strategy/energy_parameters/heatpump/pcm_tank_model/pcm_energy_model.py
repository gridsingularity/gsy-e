import json
import os
import logging

from pendulum import Duration

from gsy_framework.utils import convert_kWh_to_kJ

from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import PCMType
from gsy_e.gsy_e_core.util import gsye_root_path

lut_path = os.path.join(gsye_root_path, "resources")
log = logging.getLogger()


class PCMEnergyModel:
    """Class that handles temperature energy conversion"""

    def __init__(
        self,
        charging_time: Duration,
        volume_flow_rate_l_min: int,
        number_of_plates: int,
        pcm_type: PCMType = PCMType.OM37,
    ):
        self._number_of_plates = number_of_plates
        self._charging_energy_lut = self._read_lut(
            os.path.join(
                lut_path,
                f"charging_energy_{charging_time.minutes}min_{volume_flow_rate_l_min}"
                f"lmin_{number_of_plates}np_{pcm_type.name}.json",
            )
        )
        self._discharging_energy_lut = self._read_lut(
            os.path.join(
                lut_path,
                f"discharging_energy_{charging_time.minutes}min_{volume_flow_rate_l_min}"
                f"lmin_{number_of_plates}np_{pcm_type.name}.json",
            )
        )
        self._charging_temps = self._charging_energy_lut.keys()
        self._discharging_temps = self._discharging_energy_lut.keys()
        self._initial_temps_charge = self._charging_energy_lut[
            next(iter(self._charging_energy_lut))
        ].keys()
        self._initial_temps_discharge = self._discharging_energy_lut[
            next(iter(self._discharging_energy_lut))
        ].keys()

    def get_soc_energy_kJ(self, current_storage_temp: float, discharging_temp: float) -> float:
        """Return the energy that is available in the PCM storage."""
        initial_temp = self._find_initial_temp_discharge(current_storage_temp)
        discharging_temp = self._find_discharging_temp(discharging_temp)
        discharge_energy_kWh = self._discharging_energy_lut[discharging_temp][initial_temp]
        # we multiply with the number of plates here, because the model is only for one plate
        return convert_kWh_to_kJ(discharge_energy_kWh) * self._number_of_plates

    def get_dod_energy_kJ(self, current_storage_temp: float, charging_temp: float) -> float:
        """Return the energy that could be stored in the PCM storage."""
        initial_temp = self._find_initial_temp_charge(current_storage_temp)
        charging_temp = self._find_charging_temp(charging_temp)
        dod_energy_kWh = self._charging_energy_lut[charging_temp][initial_temp]
        # we multiply with the number of plates here, because the model is only for one plate
        return convert_kWh_to_kJ(dod_energy_kWh) * self._number_of_plates

    def _read_lut(self, filepath: str) -> dict[float, dict[float, float]]:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._convert_keys_to_float(data)

    def _convert_keys_to_float(self, obj):
        if isinstance(obj, dict):
            return {float(k): self._convert_keys_to_float(v) for k, v in obj.items()}
        return obj

    def _calc_find_in_lut(self, temperatures_in_lut, value_to_find: float) -> float:
        return float(min(temperatures_in_lut, key=lambda x: abs(x - value_to_find)))

    def _find_charging_temp(self, charging_temp: float) -> float:
        lut_charging_temp = self._calc_find_in_lut(self._charging_temps, charging_temp)
        if charging_temp < min(self._charging_temps) or charging_temp > max(self._charging_temps):
            log.error(
                "charging temperature %s is not present in LUT, using the boarder value %s",
                charging_temp,
                lut_charging_temp,
            )
        return lut_charging_temp

    def _find_discharging_temp(self, discharging_temp: float) -> float:
        lut_discharging_temp = self._calc_find_in_lut(self._discharging_temps, discharging_temp)
        if discharging_temp < min(self._discharging_temps) or discharging_temp > max(
            self._discharging_temps
        ):
            log.error(
                "discharging temperature %s is not present in LUT, using the boarder value %s",
                discharging_temp,
                lut_discharging_temp,
            )
        return lut_discharging_temp

    def _find_initial_temp_charge(self, initial_temp: float) -> float:
        lut_initial_temp = self._calc_find_in_lut(self._initial_temps_charge, initial_temp)
        if initial_temp < min(self._initial_temps_charge) or initial_temp > max(
            self._initial_temps_charge
        ):
            log.error(
                "charging initial temperature %s is not present in LUT, "
                "using the boarder value %s",
                initial_temp,
                lut_initial_temp,
            )
        return lut_initial_temp

    def _find_initial_temp_discharge(self, initial_temp: float) -> float:
        lut_initial_temp = self._calc_find_in_lut(self._initial_temps_discharge, initial_temp)
        if initial_temp < min(self._initial_temps_discharge) or initial_temp > max(
            self._initial_temps_discharge
        ):
            log.error(
                "discharging initial temperature %s is not present in LUT, "
                "using the boarder value %s",
                initial_temp,
                lut_initial_temp,
            )
        return lut_initial_temp
