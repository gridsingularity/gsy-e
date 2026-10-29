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

import json

from gsy_framework.constants_limits import ConstSettings, GlobalConfig, TIME_ZONE
from gsy_framework.exceptions import GSyException
from gsy_framework.read_user_profile import InputProfileTypes, UserProfileReader
from pendulum import DateTime, Duration, duration, today

from gsy_e.gsy_e_core.redis_connections.area_market import external_redis_communicator_factory
from gsy_e.gsy_e_core.util import change_global_config, format_interval


class SimulationConfig:
    """Class defining parameters that describe the behavior of a simulation."""

    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(
        self,
        sim_duration: duration,
        slot_length: duration,
        tick_length: duration,
        market_maker_rate=ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
        start_date: DateTime = today(tz=TIME_ZONE),
        capacity_kW=None,
        grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
        external_connection_enabled=True,
        aggregator_device_mapping=None,
        enable_degrees_of_freedom: bool = True,
        hours_of_delay: int = ConstSettings.SCMSettings.HOURS_OF_DELAY,
    ):
        """
        Args:
            sim_duration: The total duration of the simulation
            slot_length: The duration of each market slot
            tick_length: The duration of each slot tick
            market_maker_rate: The cost to buy electricity from the utility
            start_date: The start date of the simulation
            capacity_kW: The capacity of PV panels in kW
            grid_fee_type: An integer describing the type of grid fees to be applied
            external_connection_enabled: A flag to allow receiving orders from an external client
            aggregator_device_mapping: A dictionary that maps each aggregator to its devices
            enable_degrees_of_freedom: If True, allow orders to have Degrees of Freedom (they can
                specify additional requirements and attributes)
            hours_of_delay: Hours of delay
        """
        self.sim_duration = sim_duration
        self.start_date = start_date
        self.end_date = start_date + sim_duration
        self.slot_length = slot_length
        self.tick_length = tick_length
        self.grid_fee_type = grid_fee_type
        self.enable_degrees_of_freedom = enable_degrees_of_freedom
        self.market_maker_rate = market_maker_rate
        self.hours_of_delay = hours_of_delay

        self.ticks_per_slot = self.slot_length / self.tick_length
        if self.ticks_per_slot != int(self.ticks_per_slot):
            raise GSyException(
                f"Non integer ticks per slot ({self.ticks_per_slot}) are not supported. "
                "Adjust simulation parameters."
            )
        self.ticks_per_slot = int(self.ticks_per_slot)
        if self.ticks_per_slot < 10:
            raise GSyException(
                f"Too few ticks per slot ({self.ticks_per_slot}). Adjust simulation parameters"
            )
        self.total_ticks = self.sim_duration // self.slot_length * self.ticks_per_slot

        self.market_slot_list = []

        change_global_config(**self.__dict__)
        self.set_market_maker_rate(market_maker_rate)

        self.capacity_kW = capacity_kW or ConstSettings.PVSettings.DEFAULT_CAPACITY_KW
        self.external_connection_enabled = external_connection_enabled
        self.external_redis_communicator = external_redis_communicator_factory(
            external_connection_enabled
        )
        if aggregator_device_mapping:
            self.external_redis_communicator.aggregator.set_aggregator_device_mapping(
                aggregator_device_mapping
            )
        self.scm_past_slots = False

    def __repr__(self):
        return json.dumps(self.as_dict())

    def as_dict(self):
        """Return config parameters as dict."""
        fields = {
            "sim_duration",
            "slot_length",
            "tick_length",
            "ticks_per_slot",
            "total_ticks",
            "capacity_kW",
            "grid_fee_type",
            "external_connection_enabled",
            "enable_degrees_of_freedom",
            "hours_of_delay",
        }
        return {
            k: format_interval(v) if isinstance(v, Duration) else v
            for k, v in self.__dict__.items()
            if k in fields
        }

    def update_config_parameters(self, *, market_maker_rate=None, capacity_kW=None):
        """Update provided config parameters."""
        if market_maker_rate is not None:
            self.set_market_maker_rate(market_maker_rate)
        if capacity_kW is not None:
            self.capacity_kW = capacity_kW

    def set_market_maker_rate(self, market_maker_rate):
        """
        Reads market_maker_rate from arbitrary input types
        """
        self.market_maker_rate = UserProfileReader().read_arbitrary_profile(
            InputProfileTypes.IDENTITY, market_maker_rate
        )


def create_simulation_config_from_global_config():
    """
    Create a SimulationConfig object from the GlobalConfig class members.
    These 2 object are not currently in sync because the following parameters are missing from the
    GlobalConfig:
    - capacity_kW
    - external_connection_enabled
    - aggregator_device_mapping
    """
    return SimulationConfig(
        slot_length=GlobalConfig.slot_length,
        sim_duration=GlobalConfig.sim_duration,
        tick_length=GlobalConfig.tick_length,
        market_maker_rate=GlobalConfig.market_maker_rate,
        start_date=GlobalConfig.start_date,
        grid_fee_type=GlobalConfig.grid_fee_type,
        enable_degrees_of_freedom=GlobalConfig.enable_degrees_of_freedom,
    )
