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
from pendulum import duration
from collections import namedtuple
from enum import Enum
from math import isclose
from d3a_interface.constants_limits import ConstSettings
from d3a import limit_float_precision
from d3a.d3a_core.util import generate_market_slot_list

StorageSettings = ConstSettings.StorageSettings

# Complex device models should be split in three classes each:
#
# - a strategy class responsible for buying/selling options
# - an appliance class responsible for actual energy transfers (drawing/serving options)
# - a state class keeping the state of the appliance
#
# The full three-classes setup is not necessary for every device:
# - Some devices may not have a state. The state class is mainly meant to share data between
#   strategy and appliance, so simple responses to triggers and events are not part of it,
#   neither are unpredictable parameters that the strategy cannot take into account (like
#   cloud_cover in PVAppliance)
# - If a device has no state, maybe it doesn't need its own appliance class either;
#   SimpleAppliance may do.


class PVState:
    def __init__(self):
        self.available_energy_kWh = \
            {slot: 0. for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]


class LoadState:
    def __init__(self):
        self.desired_energy_Wh = \
            {slot: 0. for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        self.total_energy_demanded_wh = 0


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
                 min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC):

        initial_capacity_kWh = capacity * initial_soc / 100

        self.min_allowed_soc_ratio = min_allowed_soc / 100

        self.capacity = capacity
        self.loss_per_hour = loss_per_hour
        self.max_abs_battery_power_kW = max_abs_battery_power_kW

        # storage capacity, that is already sold:
        self.pledged_sell_kWh = \
            {slot: 0. for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        # storage capacity, that has been offered (but not traded yet):
        self.offered_sell_kWh = \
            {slot: 0. for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        # energy, that has been bought:
        self.pledged_buy_kWh = \
            {slot: 0. for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        # energy, that the storage wants to buy (but not traded yet):
        self.offered_buy_kWh = \
            {slot: 0. for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        self.time_series_ess_share = \
            {slot: {ESSEnergyOrigin.UNKNOWN: 0.,
                    ESSEnergyOrigin.LOCAL: 0.,
                    ESSEnergyOrigin.EXTERNAL: 0.}
             for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]

        self.charge_history = \
            {slot: '-' for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        self.charge_history_kWh = \
            {slot: '-' for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        self.offered_history = \
            {slot: '-' for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        self.used_history = \
            {slot: '-' for slot in generate_market_slot_list()}  # type: Dict[DateTime, float]
        self.energy_to_buy_dict = {slot: 0. for slot in generate_market_slot_list()}

        self._used_storage = initial_capacity_kWh
        self._battery_energy_per_slot = 0.0
        self._used_storage_share = [EnergyOrigin(initial_energy_origin, initial_capacity_kWh)]

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
            + self.pledged_buy_kWh[time_slot] \
            + self.offered_buy_kWh[time_slot]
        return self.capacity - in_use

    def max_offer_energy_kWh(self, time_slot):
        return self.used_storage - self.pledged_sell_kWh[time_slot] \
                                 - self.offered_sell_kWh[time_slot]

    def max_buy_energy_kWh(self, time_slot):
        return self._battery_energy_per_slot - self.pledged_buy_kWh[time_slot] \
                                             - self.offered_buy_kWh[time_slot]

    def set_battery_energy_per_slot(self, slot_length):
        self._battery_energy_per_slot = self.max_abs_battery_power_kW * \
                                        (slot_length / duration(hours=1))

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
        assert self.min_allowed_soc_ratio < charge or \
            isclose(self.min_allowed_soc_ratio, charge, rel_tol=1e-06)
        assert limit_float_precision(self.used_storage) <= self.capacity
        assert 0 <= limit_float_precision(self.offered_sell_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.pledged_sell_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.pledged_buy_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.offered_buy_kWh[time_slot]) <= max_value

    def lose(self, proportion):
        self._used_storage *= 1.0 - proportion

    def tick(self, area, time_slot):
        self.check_state(time_slot)
        self.lose(self.loss_per_hour * area.config.tick_length.in_seconds() / 3600)

    def calculate_soc_for_time_slot(self, time_slot):
        self.charge_history[time_slot] = 100.0 * self.used_storage / self.capacity
        self.charge_history_kWh[time_slot] = self.used_storage

    def market_cycle(self, past_time_slot, time_slot):
        """
        Simulate actual Energy flow by removing pledged storage and added bought energy to the
        used_storage
        """
        self._used_storage -= self.pledged_sell_kWh[past_time_slot]
        self._used_storage += self.pledged_buy_kWh[past_time_slot]

        self.calculate_soc_for_time_slot(time_slot)
        self.offered_history[time_slot] = self.offered_sell_kWh[time_slot]

        for energy_type in self._used_storage_share:
            self.time_series_ess_share[past_time_slot][energy_type.origin] += energy_type.value
