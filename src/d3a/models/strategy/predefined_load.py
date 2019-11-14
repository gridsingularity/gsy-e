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
from typing import Union
from pendulum import duration

from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import generate_market_slot_list
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.read_user_profile import read_arbitrary_profile
from d3a.models.read_user_profile import InputProfileTypes

"""
Create a load that uses a profile as input for its power values
"""


class DefinedLoadStrategy(LoadHoursStrategy):
    """
        Strategy for creating a load profile. It accepts as an input a load csv file or a
        dictionary that contains the load values for each time point
    """
    parameters = ('daily_load_profile', 'fit_to_limit', 'energy_rate_increase_per_update',
                  'update_interval', 'initial_buying_rate', 'final_buying_rate',
                  'balancing_energy_ratio', 'use_market_maker_rate')

    def __init__(self, daily_load_profile,
                 fit_to_limit=True, energy_rate_increase_per_update=1,
                 update_interval=duration(
                     minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
                 initial_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
                 final_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
                 balancing_energy_ratio: tuple =
                 (ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
                  ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO),
                 use_market_maker_rate: bool = False):
        """
        Constructor of DefinedLoadStrategy
        :param daily_load_profile: input profile for a day. Can be either a csv file path,
        or a dict with hourly data (Dict[int, float])
        or a dict with arbitrary time data (Dict[str, float])
        :param fit_to_limit: if set to True, it will make a linear curve
        following following initial_buying_rate & final_buying_rate
        :param energy_rate_increase_per_update: Slope of Load bids change per update
        :param update_interval: Interval after which Load will update its offer
        :param initial_buying_rate: Starting point of load's preferred buying rate
        :param final_buying_rate: Ending point of load's preferred buying rate
        :param balancing_energy_ratio: Portion of energy to be traded in balancing market
        :param use_market_maker_rate: If set to True, Load would track its final buying rate
        as per utility's trading rate
        """

        super().__init__(0, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate)
        self.daily_load_profile = daily_load_profile
        self.load_profile = {}

    def event_activate(self):
        """
        Runs on activate event. Reads the power profile data and calculates the required energy
        for each slot.
        :return: None
        """
        self.bid_update.update_on_activate()
        self.load_profile = read_arbitrary_profile(
            InputProfileTypes.POWER,
            self.daily_load_profile)
        self._update_energy_requirement()

    def _update_energy_requirement(self):
        """
        Update required energy values for each market slot.
        :return: None
        """
        self._simulation_start_timestamp = self.area.now
        self.hrs_per_day = {day: self._initial_hrs_per_day
                            for day in range(self.area.config.sim_duration.days + 1)}
        for slot_time in generate_market_slot_list(area=self.area):
            if self._allowed_operating_hours(slot_time.hour):
                self.energy_requirement_Wh[slot_time] = \
                    self.load_profile[slot_time] * 1000
                self.state.desired_energy_Wh[slot_time] = \
                    self.load_profile[slot_time] * 1000

    def _operating_hours(self, energy):
        """
        Disabled feature for this subclass
        """
        return 0

    def _allowed_operating_hours(self, time):
        """
        Disabled feature for this subclass
        """
        return True
