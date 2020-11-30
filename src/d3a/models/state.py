"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from pendulum import DateTime  # NOQA
from typing import Dict  # NOQA
from collections import namedtuple
from enum import Enum
from math import isclose
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.utils import convert_pendulum_to_str_in_dict, convert_str_to_pendulum_in_dict
from d3a import limit_float_precision
from d3a.d3a_core.util import write_default_to_dict, convert_kW_to_kWh

StorageSettings = ConstSettings.StorageSettings

# Complex device models should be split in three classes each:
#
# - a strategy class responsible for buying/selling options
# - an appliance class responsible for actual energy transfers (drawing/serving options)
#   (appliance class has to be reinstated if needed)
# - a state class keeping the state of the appliance
#
# The full three-classes setup is not necessary for every device:
# - Some devices may not have a state. The state class is mainly meant to share data between
#   strategy and appliance, so simple responses to triggers and events are not part of it,
#   neither are unpredictable parameters that the strategy can not take into account
# - If a device has no state, maybe it doesn't need its own appliance class either


class PVState:
    def __init__(self):
        self.available_energy_kWh = {}

    def get_state(self):
        return {"available_energy_kWh": convert_pendulum_to_str_in_dict(self.available_energy_kWh)}

    def restore_state(self, state_dict):
        self.available_energy_kWh = state_dict["available_energy_kWh"]


class LoadState:
    def __init__(self):
        self.desired_energy_Wh = {}
        self.total_energy_demanded_wh = 0

    def get_state(self):
        return {"desired_energy_Wh": convert_pendulum_to_str_in_dict(self.desired_energy_Wh)}

    def restore_state(self, state_dict):
        self.desired_energy_Wh = state_dict["desired_energy_Wh"]


class ESSEnergyOrigin(Enum):
    LOCAL = 1
    EXTERNAL = 2
    UNKNOWN = 3


EnergyOrigin = namedtuple('EnergyOrigin', ('origin', 'value'))


class StorageState:
    def __init__(self,
                 initial_soc=StorageSettings.MIN_ALLOWED_SOC,
                 initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
                 capacity=StorageSettings.CAPACITY,
                 max_abs_battery_power_kW=StorageSettings.MAX_ABS_POWER,
                 loss_per_hour=0.01,
                 loss_function=1,
                 min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC):

        self.initial_soc = initial_soc
        self.initial_capacity_kWh = capacity * initial_soc / 100

        self.min_allowed_soc_ratio = min_allowed_soc / 100

        self.capacity = capacity
        self.loss_per_hour = loss_per_hour
        self.loss_function = loss_function
        self.max_abs_battery_power_kW = max_abs_battery_power_kW

        # storage capacity, that is already sold:
        self.pledged_sell_kWh = {}
        # storage capacity, that has been offered (but not traded yet):
        self.offered_sell_kWh = {}
        # energy, that has been bought:
        self.pledged_buy_kWh = {}
        # energy, that the storage wants to buy (but not traded yet):
        self.offered_buy_kWh = {}
        self.time_series_ess_share = {}

        self.charge_history = {}
        self.charge_history_kWh = {}
        self.offered_history = {}
        self.used_history = {}  # type: Dict[DateTime, float]
        self.energy_to_buy_dict = {}
        self.energy_to_sell_dict = {}

        self._used_storage = self.initial_capacity_kWh
        self._battery_energy_per_slot = 0.0
        self._used_storage_share = [EnergyOrigin(initial_energy_origin, self.initial_capacity_kWh)]

    def get_state(self):
        return {
            "pledged_sell_kWh": convert_pendulum_to_str_in_dict(self.pledged_sell_kWh),
            "offered_sell_kWh": convert_pendulum_to_str_in_dict(self.offered_sell_kWh),
            "pledged_buy_kWh": convert_pendulum_to_str_in_dict(self.pledged_buy_kWh),
            "offered_buy_kWh": convert_pendulum_to_str_in_dict(self.offered_buy_kWh),
            "charge_history": convert_pendulum_to_str_in_dict(self.charge_history),
            "charge_history_kWh": convert_pendulum_to_str_in_dict(self.charge_history_kWh),
            "offered_history": convert_pendulum_to_str_in_dict(self.offered_history),
            "used_history": convert_pendulum_to_str_in_dict(self.used_history),
            "energy_to_buy_dict": convert_pendulum_to_str_in_dict(self.energy_to_buy_dict),
            "energy_to_sell_dict": convert_pendulum_to_str_in_dict(self.energy_to_sell_dict),
            "used_storage": self._used_storage,
            "battery_energy_per_slot": self._battery_energy_per_slot,
        }

    def restore_state(self, state_dict):
        self.pledged_sell_kWh = convert_str_to_pendulum_in_dict(state_dict["pledged_sell_kWh"])
        self.offered_sell_kWh = convert_str_to_pendulum_in_dict(state_dict["offered_sell_kWh"])
        self.pledged_buy_kWh = convert_str_to_pendulum_in_dict(state_dict["pledged_buy_kWh"])
        self.offered_buy_kWh = convert_str_to_pendulum_in_dict(state_dict["offered_buy_kWh"])
        self.charge_history = convert_str_to_pendulum_in_dict(state_dict["charge_history"])
        self.charge_history_kWh = convert_str_to_pendulum_in_dict(state_dict["charge_history_kWh"])
        self.offered_history = convert_str_to_pendulum_in_dict(state_dict["offered_history"])
        self.used_history = convert_str_to_pendulum_in_dict(state_dict["used_history"])
        self.energy_to_buy_dict = convert_str_to_pendulum_in_dict(state_dict["energy_to_buy_dict"])
        self.energy_to_sell_dict = convert_str_to_pendulum_in_dict(
            state_dict["energy_to_sell_dict"])
        self._used_storage = state_dict["used_storage"]
        self._battery_energy_per_slot = state_dict["battery_energy_per_slot"]

    @property
    def used_storage(self):
        """
        Current stored energy
        """
        return self._used_storage

    def update_used_storage_share(self, energy, source=ESSEnergyOrigin.UNKNOWN):
        self._used_storage_share.append(EnergyOrigin(source, energy))

    @property
    def get_used_storage_share(self):
        return self._used_storage_share

    def free_storage(self, time_slot):
        """
        Storage, that has not been promised or occupied
        """
        in_use = self._used_storage \
            - self.pledged_sell_kWh[time_slot] \
            + self.pledged_buy_kWh[time_slot]
        return self.capacity - in_use

    def max_offer_energy_kWh(self, time_slot):
        return self._battery_energy_per_slot - self.pledged_sell_kWh[time_slot] \
               - self.offered_sell_kWh[time_slot]

    def max_buy_energy_kWh(self, time_slot):
        return self._battery_energy_per_slot - self.pledged_buy_kWh[time_slot] \
               - self.offered_buy_kWh[time_slot]

    def set_battery_energy_per_slot(self, slot_length):
        self._battery_energy_per_slot = convert_kW_to_kWh(self.max_abs_battery_power_kW,
                                                          slot_length)

    def has_battery_reached_max_power(self, energy, time_slot):
        return limit_float_precision(abs(energy
                                     + self.pledged_sell_kWh[time_slot]
                                     + self.offered_sell_kWh[time_slot]
                                     - self.pledged_buy_kWh[time_slot]
                                     - self.offered_buy_kWh[time_slot])) > \
               self._battery_energy_per_slot

    def clamp_energy_to_sell_kWh(self, market_slot_time_list):
        """
        Determines available energy to sell for each active market and returns a dict[TIME, FLOAT]
        """
        accumulated_pledged = 0
        accumulated_offered = 0
        for time_slot in market_slot_time_list:
            accumulated_pledged += self.pledged_sell_kWh[time_slot]
            accumulated_offered += self.offered_sell_kWh[time_slot]

        energy = self.used_storage \
            - accumulated_pledged \
            - accumulated_offered \
            - self.min_allowed_soc_ratio * self.capacity
        storage_dict = {}
        for time_slot in market_slot_time_list:
            storage_dict[time_slot] = limit_float_precision(min(
                                                            energy / len(market_slot_time_list),
                                                            self.max_offer_energy_kWh(time_slot),
                                                            self._battery_energy_per_slot))
            self.energy_to_sell_dict[time_slot] = storage_dict[time_slot]

        return storage_dict

    def clamp_energy_to_buy_kWh(self, market_slot_time_list):
        """
        Determines amount of energy that can be bought for each active market and writes it to
        self.energy_to_buy_dict
        """

        accumulated_bought = 0
        accumulated_sought = 0
        for time_slot in market_slot_time_list:
            accumulated_bought += self.pledged_buy_kWh[time_slot]
            accumulated_sought += self.offered_buy_kWh[time_slot]
        energy = limit_float_precision((self.capacity
                                        - self.used_storage
                                        - accumulated_bought
                                        - accumulated_sought) / len(market_slot_time_list))

        for time_slot in market_slot_time_list:
            clamped_energy = limit_float_precision(
                min(energy, self.max_buy_energy_kWh(time_slot), self._battery_energy_per_slot))
            clamped_energy = max(clamped_energy, 0)
            self.energy_to_buy_dict[time_slot] = clamped_energy

    def check_state(self, time_slot):
        """
        Sanity check of the state variables.
        """
        charge = limit_float_precision(self.used_storage / self.capacity)
        max_value = self.capacity - self.min_allowed_soc_ratio * self.capacity
        assert self.min_allowed_soc_ratio <= charge or \
            isclose(self.min_allowed_soc_ratio, charge, rel_tol=1e-06)
        assert limit_float_precision(self.used_storage) <= self.capacity
        assert 0 <= limit_float_precision(self.offered_sell_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.pledged_sell_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.pledged_buy_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.offered_buy_kWh[time_slot]) <= max_value

    def lose(self, loss_function, loss_per_hour):
        if loss_function == 1:
            if self._used_storage * (1.0 - loss_per_hour) >= 0:
                self._used_storage *= 1.0 - loss_per_hour
            else:
                self._used_storage = 0
        else:
            if self._used_storage >= loss_per_hour:
                self._used_storage += - loss_per_hour
            else:
                self._used_storage = 0

    def tick(self, area, time_slot):
        self.check_state(time_slot)
        self.lose(self.loss_function,
                  self.loss_per_hour * area.config.tick_length.in_seconds() / 3600)

    def calculate_soc_for_time_slot(self, time_slot):
        self.charge_history[time_slot] = 100.0 * self.used_storage / self.capacity
        self.charge_history_kWh[time_slot] = self.used_storage

    def add_default_values_to_state_profiles(self, area):
        for market in area.all_markets:
            time_slot = market.time_slot
            write_default_to_dict(self.pledged_sell_kWh, time_slot, 0)
            write_default_to_dict(self.pledged_buy_kWh, time_slot, 0)
            write_default_to_dict(self.offered_sell_kWh, time_slot, 0)
            write_default_to_dict(self.offered_buy_kWh, time_slot, 0)

            write_default_to_dict(self.charge_history, time_slot, self.initial_soc)
            write_default_to_dict(self.charge_history_kWh, time_slot, self.initial_capacity_kWh)

            write_default_to_dict(self.energy_to_buy_dict, time_slot, 0)
            write_default_to_dict(self.energy_to_sell_dict, time_slot, 0)
            write_default_to_dict(self.offered_history, time_slot, '-')
            write_default_to_dict(self.used_history, time_slot, '-')

            write_default_to_dict(self.time_series_ess_share, time_slot,
                                  {ESSEnergyOrigin.UNKNOWN: 0.,
                                   ESSEnergyOrigin.LOCAL: 0.,
                                   ESSEnergyOrigin.EXTERNAL: 0.})

    def market_cycle(self, past_time_slot, time_slot):
        """
        Simulate actual Energy flow by removing pledged storage and added bought energy to the
        used_storage
        """
        if past_time_slot:
            self._used_storage -= self.pledged_sell_kWh[past_time_slot]
            self._used_storage += self.pledged_buy_kWh[past_time_slot]

        self.calculate_soc_for_time_slot(time_slot)
        self.offered_history[time_slot] = self.offered_sell_kWh[time_slot]

        if past_time_slot:
            for energy_type in self._used_storage_share:
                self.time_series_ess_share[past_time_slot][energy_type.origin] += energy_type.value
