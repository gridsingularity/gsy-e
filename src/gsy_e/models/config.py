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
import ast
import json

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.exceptions import GSyException
from gsy_framework.read_user_profile import (
    InputProfileTypes, read_and_convert_identity_profile_to_float, read_arbitrary_profile)
from pendulum import DateTime, Duration, duration, today

from gsy_e.constants import TIME_ZONE
from gsy_e.gsy_e_core.redis_connections.redis_area_market_communicator import (
    external_redis_communicator_factory)
from gsy_e.gsy_e_core.util import change_global_config, format_interval


class SimulationConfig:
    """Class defining parameters that describe the behavior of a simulation."""
    def __init__(self, sim_duration: duration, slot_length: duration, tick_length: duration,
                 cloud_coverage: int,
                 market_maker_rate=ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
                 pv_user_profile=None, start_date: DateTime = today(tz=TIME_ZONE),
                 capacity_kW=None, grid_fee_type=ConstSettings.MASettings.GRID_FEE_TYPE,
                 external_connection_enabled=True, aggregator_device_mapping=None,
                 enable_degrees_of_freedom: bool = True):
        """
        Args:
            sim_duration: The total duration of the simulation
            slot_length: The duration of each market slot
            tick_length: The duration of each slot tick
            cloud_coverage: An integer to define the sky conditions
                (see ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
            market_maker_rate: The cost to buy electricity from the utility
            pv_user_profile: A custom PV profile provided by the user
            start_date: The start date of the simulation
            capacity_kW: The capacity of PV panels in kW
            grid_fee_type: An integer describing the type of grid fees to be applied
            external_connection_enabled: A flag to allow receiving orders from an external client
            aggregator_device_mapping: A dictionary that maps each aggregator to its devices
            enable_degrees_of_freedom: If True, allow orders to have Degrees of Freedom (they can
                specify additional requirements and attributes)
        """
        self.sim_duration = sim_duration
        self.start_date = start_date
        self.end_date = start_date + sim_duration
        self.slot_length = slot_length
        self.tick_length = tick_length
        self.grid_fee_type = grid_fee_type
        self.enable_degrees_of_freedom = enable_degrees_of_freedom

        self.ticks_per_slot = self.slot_length / self.tick_length
        if self.ticks_per_slot != int(self.ticks_per_slot):
            raise GSyException(
                f"Non integer ticks per slot ({self.ticks_per_slot}) are not supported. "
                "Adjust simulation parameters.")
        self.ticks_per_slot = int(self.ticks_per_slot)
        if self.ticks_per_slot < 10:
            raise GSyException(
                f"Too few ticks per slot ({self.ticks_per_slot}). Adjust simulation parameters")
        self.total_ticks = self.sim_duration // self.slot_length * self.ticks_per_slot

        self.cloud_coverage = cloud_coverage

        self.market_slot_list = []

        change_global_config(**self.__dict__)
        self.read_pv_user_profile(pv_user_profile)
        self.read_market_maker_rate(market_maker_rate)

        self.capacity_kW = capacity_kW or ConstSettings.PVSettings.DEFAULT_CAPACITY_KW
        self.external_connection_enabled = external_connection_enabled
        self.external_redis_communicator = external_redis_communicator_factory(
            external_connection_enabled)
        if aggregator_device_mapping is not None:
            self.external_redis_communicator.aggregator.set_aggregator_device_mapping(
                aggregator_device_mapping
            )

    def __repr__(self):
        return json.dumps(self.as_dict())

    def as_dict(self):
        """Return config parameters as dict."""
        fields = {"sim_duration", "slot_length", "tick_length", "ticks_per_slot",
                  "total_ticks", "cloud_coverage", "capacity_kW", "grid_fee_type",
                  "external_connection_enabled", "enable_degrees_of_freedom"}
        return {
            k: format_interval(v) if isinstance(v, Duration) else v
            for k, v in self.__dict__.items()
            if k in fields
        }

    def update_config_parameters(self, *, cloud_coverage=None, pv_user_profile=None,
                                 market_maker_rate=None, capacity_kW=None):
        """Update provided config parameters."""
        if cloud_coverage is not None:
            self.cloud_coverage = cloud_coverage
        if pv_user_profile is not None:
            self.read_pv_user_profile(pv_user_profile)
        if market_maker_rate is not None:
            self.read_market_maker_rate(market_maker_rate)
        if capacity_kW is not None:
            self.capacity_kW = capacity_kW

    def read_pv_user_profile(self, pv_user_profile=None):
        """Read global pv user profile."""
        self.pv_user_profile = None \
            if pv_user_profile is None \
            else read_arbitrary_profile(InputProfileTypes.POWER,
                                        ast.literal_eval(pv_user_profile))

    def read_market_maker_rate(self, market_maker_rate):
        """
        Reads market_maker_rate from arbitrary input types
        """
        self.market_maker_rate = read_and_convert_identity_profile_to_float(market_maker_rate)
