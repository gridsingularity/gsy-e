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
import ast
from pendulum import duration, Duration, DateTime, today

from d3a.constants import TIME_ZONE
from d3a.d3a_core.exceptions import D3AException
from d3a.d3a_core.util import format_interval
from d3a_interface.constants_limits import ConstSettings
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes, \
    read_and_convert_identity_profile_to_float
from d3a.d3a_core.util import change_global_config
from d3a.d3a_core.redis_connections.redis_area_market_communicator import \
    CommonResettableCommunicator


class SimulationConfig:
    def __init__(self, sim_duration: duration, slot_length: duration, tick_length: duration,
                 market_count: int, cloud_coverage: int,
                 market_maker_rate=ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
                 pv_user_profile=None, start_date: DateTime=today(tz=TIME_ZONE),
                 max_panel_power_W=None, grid_fee_type=ConstSettings.IAASettings.GRID_FEE_TYPE):

        self.sim_duration = sim_duration
        self.start_date = start_date
        self.end_date = start_date + sim_duration
        self.slot_length = slot_length
        self.tick_length = tick_length
        self.market_count = market_count
        self.grid_fee_type = grid_fee_type
        self.ticks_per_slot = self.slot_length / self.tick_length
        if self.ticks_per_slot != int(self.ticks_per_slot):
            raise D3AException(
                "Non integer ticks per slot ({}) are not supported. "
                "Adjust simulation parameters.".format(self.ticks_per_slot))
        self.ticks_per_slot = int(self.ticks_per_slot)
        if self.ticks_per_slot < 10:
            raise D3AException("Too few ticks per slot ({}). Adjust simulation parameters".format(
                self.ticks_per_slot
            ))
        self.total_ticks = self.sim_duration // self.slot_length * self.ticks_per_slot

        self.cloud_coverage = cloud_coverage

        self.market_slot_list = []

        change_global_config(**self.__dict__)
        self.read_pv_user_profile(pv_user_profile)
        self.read_market_maker_rate(market_maker_rate)

        max_panel_power_W = ConstSettings.PVSettings.MAX_PANEL_OUTPUT_W \
            if max_panel_power_W is None else max_panel_power_W
        self.max_panel_power_W = max_panel_power_W
        self.external_redis_communicator = CommonResettableCommunicator()

    def __repr__(self):
        return (
            "<SimulationConfig("
            "sim_duration='{s.sim_duration}', "
            "slot_length='{s.slot_length}', "
            "tick_length='{s.tick_length}', "
            "market_count='{s.market_count}', "
            "ticks_per_slot='{s.ticks_per_slot}', "
            "cloud_coverage='{s.cloud_coverage}', "
            "pv_user_profile='{s.pv_user_profile}', "
            "max_panel_power_W='{s.max_panel_power_W}', "
            "grid_fee_type='{s.grid_fee_type}', "
            ")>"
        ).format(s=self)

    def as_dict(self):
        fields = {'sim_duration', 'slot_length', 'tick_length', 'market_count', 'ticks_per_slot',
                  'total_ticks', 'cloud_coverage', 'max_panel_power_W', 'grid_fee_type'}
        return {
            k: format_interval(v) if isinstance(v, Duration) else v
            for k, v in self.__dict__.items()
            if k in fields
        }

    def update_config_parameters(self, cloud_coverage=None, pv_user_profile=None,
                                 market_maker_rate=None, max_panel_power_W=None):
        if cloud_coverage is not None:
            self.cloud_coverage = cloud_coverage
        if pv_user_profile is not None:
            self.read_pv_user_profile(pv_user_profile)
        if market_maker_rate is not None:
            self.read_market_maker_rate(market_maker_rate)
        if max_panel_power_W is not None:
            self.max_panel_power_W = max_panel_power_W

    def read_pv_user_profile(self, pv_user_profile=None):
        self.pv_user_profile = None \
            if pv_user_profile is None \
            else read_arbitrary_profile(InputProfileTypes.POWER,
                                        ast.literal_eval(pv_user_profile))

    def read_market_maker_rate(self, market_maker_rate):
        """
        Reads market_maker_rate from arbitrary input types
        """
        self.market_maker_rate = read_and_convert_identity_profile_to_float(market_maker_rate)
