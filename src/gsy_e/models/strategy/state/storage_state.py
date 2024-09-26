"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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

from collections import namedtuple
from enum import Enum
from math import isclose
from typing import Dict, List, Optional
from dataclasses import dataclass

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.utils import (
    convert_pendulum_to_str_in_dict,
    convert_str_to_pendulum_in_dict,
    convert_kW_to_kWh,
    limit_float_precision,
)
from pendulum import DateTime

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.gsy_e_core.util import is_time_slot_in_past_markets, write_default_to_dict
from gsy_e.models.strategy.state.base_states import StateInterface

StorageSettings = ConstSettings.StorageSettings


class ESSEnergyOrigin(Enum):
    """Enum for the storage's possible sources of energy."""

    LOCAL = 1
    EXTERNAL = 2
    UNKNOWN = 3


EnergyOrigin = namedtuple("EnergyOrigin", ("origin", "value"))


@dataclass
class StorageLosses:
    """Container for all loss related Storage settings."""

    charging_loss_percent: float = 0.0
    discharging_loss_percent: float = 0.0
    self_discharge_per_day_kWh: float = 0.0


# pylint: disable= too-many-instance-attributes, too-many-arguments, too-many-public-methods
class StorageState(StateInterface):
    """State for the storage asset."""

    def __init__(
        self,
        initial_soc=StorageSettings.MIN_ALLOWED_SOC,
        initial_energy_origin=ESSEnergyOrigin.EXTERNAL,
        capacity=StorageSettings.CAPACITY,
        max_abs_battery_power_kW=StorageSettings.MAX_ABS_POWER,
        min_allowed_soc=StorageSettings.MIN_ALLOWED_SOC,
        losses: Optional[StorageLosses] = StorageLosses(),
    ):

        self.initial_soc = initial_soc
        self.initial_capacity_kWh = capacity * initial_soc / 100

        self.min_allowed_soc_ratio = min_allowed_soc / 100

        self.capacity = capacity
        self.max_abs_battery_power_kW = max_abs_battery_power_kW

        self.losses = losses

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
        self.energy_to_buy_dict = {}
        self.energy_to_sell_dict = {}

        self._used_storage = self.initial_capacity_kWh
        self._battery_energy_per_slot = 0.0
        self.initial_energy_origin = initial_energy_origin
        self._used_storage_share = [EnergyOrigin(initial_energy_origin, self.initial_capacity_kWh)]
        self._current_market_slot = None

    def get_state(self) -> Dict:
        return {
            "pledged_sell_kWh": convert_pendulum_to_str_in_dict(self.pledged_sell_kWh),
            "offered_sell_kWh": convert_pendulum_to_str_in_dict(self.offered_sell_kWh),
            "pledged_buy_kWh": convert_pendulum_to_str_in_dict(self.pledged_buy_kWh),
            "offered_buy_kWh": convert_pendulum_to_str_in_dict(self.offered_buy_kWh),
            "charge_history": convert_pendulum_to_str_in_dict(self.charge_history),
            "charge_history_kWh": convert_pendulum_to_str_in_dict(self.charge_history_kWh),
            "offered_history": convert_pendulum_to_str_in_dict(self.offered_history),
            "energy_to_buy_dict": convert_pendulum_to_str_in_dict(self.energy_to_buy_dict),
            "energy_to_sell_dict": convert_pendulum_to_str_in_dict(self.energy_to_sell_dict),
            "used_storage": self._used_storage,
            "battery_energy_per_slot": self._battery_energy_per_slot,
        }

    def restore_state(self, state_dict: Dict):
        self.pledged_sell_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["pledged_sell_kWh"])
        )
        self.offered_sell_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["offered_sell_kWh"])
        )
        self.pledged_buy_kWh.update(convert_str_to_pendulum_in_dict(state_dict["pledged_buy_kWh"]))
        self.offered_buy_kWh.update(convert_str_to_pendulum_in_dict(state_dict["offered_buy_kWh"]))
        self.charge_history.update(convert_str_to_pendulum_in_dict(state_dict["charge_history"]))
        self.charge_history_kWh.update(
            convert_str_to_pendulum_in_dict(state_dict["charge_history_kWh"])
        )
        self.offered_history.update(convert_str_to_pendulum_in_dict(state_dict["offered_history"]))
        self.energy_to_buy_dict.update(
            convert_str_to_pendulum_in_dict(state_dict["energy_to_buy_dict"])
        )
        self.energy_to_sell_dict.update(
            convert_str_to_pendulum_in_dict(state_dict["energy_to_sell_dict"])
        )
        self._used_storage = state_dict["used_storage"]
        self._battery_energy_per_slot = state_dict["battery_energy_per_slot"]

    @property
    def used_storage(self):
        """
        Current stored energy
        """
        return self._used_storage

    def free_storage(self, time_slot):
        """
        Storage, that has not been promised or occupied
        """
        in_use = (
            self._used_storage - self.pledged_sell_kWh[time_slot] + self.pledged_buy_kWh[time_slot]
        )
        return self.capacity - in_use

    def _max_offer_energy_kWh(self, time_slot: DateTime) -> float:
        """Return the max tracked offered energy."""
        energy_kWh = (
            self._battery_energy_per_slot
            - self.pledged_sell_kWh[time_slot]
            - self.offered_sell_kWh[time_slot]
        )
        assert energy_kWh >= -FLOATING_POINT_TOLERANCE
        return energy_kWh

    def _max_buy_energy_kWh(self, time_slot: DateTime) -> float:
        """Return the min tracked bid energy."""
        energy_kWh = (
            self._battery_energy_per_slot
            - self.pledged_buy_kWh[time_slot]
            - self.offered_buy_kWh[time_slot]
        )
        assert energy_kWh >= -FLOATING_POINT_TOLERANCE
        return energy_kWh

    def activate(self, slot_length: int, current_time_slot: DateTime) -> None:
        """Set the battery energy in kWh per current time_slot."""
        self._battery_energy_per_slot = convert_kW_to_kWh(
            self.max_abs_battery_power_kW, slot_length
        )
        self._current_market_slot = current_time_slot

    def _has_battery_reached_max_discharge_power(self, energy: float, time_slot: DateTime) -> bool:
        """Check whether the storage can withhold the passed energy discharge value."""
        energy_balance_kWh = abs(
            energy
            + self.pledged_sell_kWh[time_slot]
            + self.offered_sell_kWh[time_slot]
            - self.pledged_buy_kWh[time_slot]
            - self.offered_buy_kWh[time_slot]
        )
        return energy_balance_kWh - self._battery_energy_per_slot > FLOATING_POINT_TOLERANCE

    def _has_battery_reached_max_charge_power(self, energy: float, time_slot: DateTime) -> bool:
        """Check whether the storage can withhold the passed energy charge value."""
        energy_balance_kWh = abs(
            energy
            + self.pledged_buy_kWh[time_slot]
            + self.offered_buy_kWh[time_slot]
            - self.pledged_sell_kWh[time_slot]
            - self.offered_sell_kWh[time_slot]
        )
        return energy_balance_kWh - self._battery_energy_per_slot > FLOATING_POINT_TOLERANCE

    def _clamp_energy_to_sell_kWh(self, market_slot_time_list):
        """
        Determines available energy to sell for each active market and returns a dict[TIME, FLOAT]
        """
        accumulated_pledged = 0
        accumulated_offered = 0
        for time_slot, offered_sell_energy in self.offered_sell_kWh.items():
            if time_slot >= self._current_market_slot:
                accumulated_pledged += self.pledged_sell_kWh[time_slot]
                accumulated_offered += offered_sell_energy

        available_energy_for_all_slots = (
            self.used_storage
            - accumulated_pledged
            - accumulated_offered
            - self.min_allowed_soc_ratio * self.capacity
        )

        storage_dict = {}
        for time_slot in market_slot_time_list:
            if available_energy_for_all_slots < -FLOATING_POINT_TOLERANCE:
                break
            storage_dict[time_slot] = limit_float_precision(
                min(
                    available_energy_for_all_slots,
                    self._max_offer_energy_kWh(time_slot),
                    self._battery_energy_per_slot,
                )
            )
            self.energy_to_sell_dict[time_slot] = storage_dict[time_slot]
            available_energy_for_all_slots -= storage_dict[time_slot]
        return storage_dict

    def _clamp_energy_to_buy_kWh(self, market_slot_time_list):
        """
        Determines amount of energy that can be bought for each active market and writes it to
        self.energy_to_buy_dict
        """

        accumulated_bought = 0
        accumulated_sought = 0

        for time_slot, offered_buy_energy in self.offered_buy_kWh.items():
            if time_slot >= self._current_market_slot:
                accumulated_bought += self.pledged_buy_kWh[time_slot]
                accumulated_sought += offered_buy_energy
        available_energy_for_all_slots = limit_float_precision(
            self.capacity - self.used_storage - accumulated_bought - accumulated_sought
        )

        for time_slot in market_slot_time_list:
            if available_energy_for_all_slots < -FLOATING_POINT_TOLERANCE:
                break
            clamped_energy = limit_float_precision(
                min(
                    available_energy_for_all_slots,
                    self._max_buy_energy_kWh(time_slot),
                    self._battery_energy_per_slot,
                )
            )
            clamped_energy = max(clamped_energy, 0)
            self.energy_to_buy_dict[time_slot] = clamped_energy
            available_energy_for_all_slots -= clamped_energy

    def check_state(self, time_slot):
        """
        Sanity check of the state variables.
        """
        self._clamp_energy_to_sell_kWh([time_slot])
        self._clamp_energy_to_buy_kWh([time_slot])
        self._calculate_and_update_soc(time_slot)
        charge = (
            limit_float_precision(self.used_storage / self.capacity) if self.capacity > 0 else 0
        )
        max_value = self.capacity - self.min_allowed_soc_ratio * self.capacity
        assert self.min_allowed_soc_ratio <= charge or isclose(
            self.min_allowed_soc_ratio, charge, rel_tol=1e-06
        ), f"Battery charge ({charge}) less than min soc ({self.min_allowed_soc_ratio})"
        assert limit_float_precision(self.used_storage) <= self.capacity or isclose(
            self.used_storage, self.capacity, rel_tol=1e-06
        ), f"Battery used_storage ({self.used_storage}) surpassed the capacity ({self.capacity})"

        assert 0 <= limit_float_precision(self.offered_sell_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.pledged_sell_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.pledged_buy_kWh[time_slot]) <= max_value
        assert 0 <= limit_float_precision(self.offered_buy_kWh[time_slot]) <= max_value

    def _calculate_and_update_soc(self, time_slot: DateTime) -> None:
        """Calculate the soc of the storage and update the soc history."""
        if self.capacity > 0:
            self.charge_history[time_slot] = 100.0 * self.used_storage / self.capacity
        self.charge_history_kWh[time_slot] = self.used_storage

    def add_default_values_to_state_profiles(self, future_time_slots: List):
        """Add default values to the state profiles if time_slot key doesn't exist."""
        for time_slot in future_time_slots:
            write_default_to_dict(self.pledged_sell_kWh, time_slot, 0)
            write_default_to_dict(self.pledged_buy_kWh, time_slot, 0)
            write_default_to_dict(self.offered_sell_kWh, time_slot, 0)
            write_default_to_dict(self.offered_buy_kWh, time_slot, 0)

            write_default_to_dict(self.charge_history, time_slot, self.initial_soc)
            write_default_to_dict(self.charge_history_kWh, time_slot, self.initial_capacity_kWh)

            write_default_to_dict(self.energy_to_buy_dict, time_slot, 0)
            write_default_to_dict(self.energy_to_sell_dict, time_slot, 0)
            write_default_to_dict(self.offered_history, time_slot, "-")

            write_default_to_dict(
                self.time_series_ess_share,
                time_slot,
                {
                    ESSEnergyOrigin.UNKNOWN: 0.0,
                    ESSEnergyOrigin.LOCAL: 0.0,
                    ESSEnergyOrigin.EXTERNAL: 0.0,
                },
            )

    def market_cycle(
        self, past_time_slot, current_time_slot: DateTime, all_future_time_slots: List[DateTime]
    ):
        """
        Simulate actual Energy flow by removing pledged storage and adding bought energy to the
        used_storage
        """
        self._current_market_slot = current_time_slot
        if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS:
            # In case the future market is enabled, the future orders have to be deleted once
            # the market becomes a spot market
            self.offered_buy_kWh[current_time_slot] = 0
            self.offered_sell_kWh[current_time_slot] = 0
        self.add_default_values_to_state_profiles(all_future_time_slots)

        if past_time_slot:
            self._used_storage -= self.pledged_sell_kWh[past_time_slot]
            self._used_storage += self.pledged_buy_kWh[past_time_slot]
            self._apply_losses_at_market_cycle(
                self.pledged_sell_kWh[past_time_slot], self.pledged_buy_kWh[past_time_slot]
            )

        self._clamp_energy_to_sell_kWh([current_time_slot, *all_future_time_slots])
        self._clamp_energy_to_buy_kWh([current_time_slot, *all_future_time_slots])
        self._calculate_and_update_soc(current_time_slot)

        self.offered_history[current_time_slot] = self.offered_sell_kWh[current_time_slot]

        if past_time_slot:
            for energy_type in self._used_storage_share:
                self.time_series_ess_share[past_time_slot][energy_type.origin] += energy_type.value

    def _apply_losses_at_market_cycle(self, sold_energy_kWh: float, bought_energy_kWh: float):

        charging_loss_kWh = bought_energy_kWh * self.losses.charging_loss_percent
        discharging_loss_kWh = sold_energy_kWh * self.losses.discharging_loss_percent
        self_discharging_kWh = (
            self.losses.self_discharge_per_day_kWh * GlobalConfig.slot_length.total_days()
        )
        total_loss_kWh = charging_loss_kWh + discharging_loss_kWh + self_discharging_kWh

        self._used_storage -= total_loss_kWh

    def delete_past_state_values(self, current_time_slot: DateTime):
        """
        Clean up values from past market slots that are not used anymore. Useful for
        deallocating memory that is not used anymore.
        """
        to_delete = []
        for market_slot in self.pledged_sell_kWh:
            if is_time_slot_in_past_markets(market_slot, current_time_slot):
                to_delete.append(market_slot)
        for market_slot in to_delete:
            self.pledged_sell_kWh.pop(market_slot, None)
            self.offered_sell_kWh.pop(market_slot, None)
            self.pledged_buy_kWh.pop(market_slot, None)
            self.offered_buy_kWh.pop(market_slot, None)
            self.charge_history.pop(market_slot, None)
            self.charge_history_kWh.pop(market_slot, None)
            self.offered_history.pop(market_slot, None)
            self.energy_to_buy_dict.pop(market_slot, None)
            self.energy_to_sell_dict.pop(market_slot, None)

    def register_energy_from_posted_bid(self, energy: float, time_slot: DateTime):
        """Register the energy from a posted bid on the market."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_buy_kWh[time_slot] += energy
        self._clamp_energy_to_buy_kWh([time_slot])

    def register_energy_from_posted_offer(self, energy: float, time_slot: DateTime):
        """Register the energy from a posted offer on the market."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_sell_kWh[time_slot] += energy
        self._clamp_energy_to_sell_kWh([time_slot])

    def reset_offered_sell_energy(self, energy: float, time_slot: DateTime):
        """Reset the offered sell energy amount."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_sell_kWh[time_slot] = energy
        self._clamp_energy_to_sell_kWh([time_slot])

    def reset_offered_buy_energy(self, energy: float, time_slot: DateTime):
        """Reset the offered buy energy amount."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_buy_kWh[time_slot] = energy
        self._clamp_energy_to_buy_kWh([time_slot])

    def remove_energy_from_deleted_offer(self, energy: float, time_slot: DateTime):
        """
        Unregister the energy from a deleted offer, in order to be available for following offers.
        """
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.offered_sell_kWh[time_slot] -= energy
        self._clamp_energy_to_sell_kWh([time_slot])

    def register_energy_from_one_sided_market_accept_offer(
        self,
        energy: float,
        time_slot: DateTime,
        energy_origin: ESSEnergyOrigin = ESSEnergyOrigin.UNKNOWN,
    ):
        """
        Register energy from one sided market accept offer operation. Similar behavior as
        register_energy_from_bid_trade with the exception that offered_buy_kWh is not used in
        one-sided markets (because there is no concept of bid, the storage never actually offers
        energy, the buyers with access to the market can accept it).
        """
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.pledged_buy_kWh[time_slot] += energy
        self._track_energy_bought_type(energy, energy_origin)
        self._clamp_energy_to_buy_kWh([time_slot])

    def register_energy_from_bid_trade(
        self,
        energy: float,
        time_slot: DateTime,
        energy_origin: ESSEnergyOrigin = ESSEnergyOrigin.UNKNOWN,
    ):
        """Register energy from a bid trade event."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.pledged_buy_kWh[time_slot] += energy
        self.offered_buy_kWh[time_slot] -= energy
        self._track_energy_bought_type(energy, energy_origin)
        self._clamp_energy_to_buy_kWh([time_slot])

    def register_energy_from_offer_trade(self, energy: float, time_slot: DateTime):
        """Register energy from an offer trade event."""
        assert energy >= -FLOATING_POINT_TOLERANCE
        self.pledged_sell_kWh[time_slot] += energy
        self.offered_sell_kWh[time_slot] -= energy
        self._track_energy_sell_type(energy)
        self._clamp_energy_to_sell_kWh([time_slot])

    def _track_energy_bought_type(self, energy: float, energy_origin: ESSEnergyOrigin):
        self._used_storage_share.append(EnergyOrigin(energy_origin, energy))

    # ESS Energy being utilized based on FIRST-IN FIRST-OUT mechanism
    def _track_energy_sell_type(self, energy: float):
        while limit_float_precision(energy) > 0 and len(self._used_storage_share) > 0:
            first_in_energy_with_origin = self._used_storage_share[0]
            if energy >= first_in_energy_with_origin.value:
                energy -= first_in_energy_with_origin.value
                self._used_storage_share.pop(0)
            elif energy < first_in_energy_with_origin.value:
                residual = first_in_energy_with_origin.value - energy
                self._used_storage_share[0] = EnergyOrigin(
                    first_in_energy_with_origin.origin, residual
                )
                energy = 0

    def get_available_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Retrieve the amount of energy that the storage can buy in the given time slot."""
        if self.free_storage(time_slot) == 0:
            return 0.0

        self._clamp_energy_to_buy_kWh([time_slot])
        energy_kWh = self.energy_to_buy_dict[time_slot]
        if self._has_battery_reached_max_charge_power(abs(energy_kWh), time_slot):
            return 0.0
        assert energy_kWh > -FLOATING_POINT_TOLERANCE
        return energy_kWh

    def get_available_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """Retrieve the amount of energy that the storage can sell in the given time slot."""
        if self.used_storage == 0:
            return 0.0
        energy_sell_dict = self._clamp_energy_to_sell_kWh([time_slot])
        energy_kWh = energy_sell_dict[time_slot]
        if self._has_battery_reached_max_discharge_power(energy_kWh, time_slot):
            return 0.0
        assert energy_kWh >= -FLOATING_POINT_TOLERANCE
        return energy_kWh

    def get_soc_level(self, time_slot: DateTime) -> float:
        """Get the SOC level of the storage, in percentage units."""
        if self.charge_history[time_slot] == "-" and self.capacity > 0:
            return self.used_storage / self.capacity
        return self.charge_history[time_slot] / 100.0

    def to_dict(self, time_slot: DateTime) -> Dict:
        """Get a dict with the current stats of the storage according to timeslot."""
        return {
            "energy_to_sell": self.energy_to_sell_dict[time_slot],
            "energy_active_in_bids": self.offered_buy_kWh[time_slot],
            "energy_to_buy": self.energy_to_buy_dict[time_slot],
            "energy_active_in_offers": self.offered_sell_kWh[time_slot],
            "free_storage": self.free_storage(time_slot),
            "used_storage": self.used_storage,
        }

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        return {"soc_history_%": self.charge_history.get(current_time_slot, 0)}
