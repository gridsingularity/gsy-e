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

from d3a_interface.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.utils import key_in_dict_and_not_none, find_object_of_same_weekday_and_time
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.d3a_core.exceptions import D3AException
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
                 fit_to_limit=True, energy_rate_increase_per_update=None,
                 update_interval=None,
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
        if update_interval is None:
            update_interval = \
                duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        super().__init__(avg_power_W=0, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate)
        self.daily_load_profile = daily_load_profile
        self.load_profile = {}

    def event_activate_energy(self):
        """
        Runs on activate event.
        :return: None
        """
        self._event_activate_energy(self.daily_load_profile)
        super().event_activate_energy()
        del self.daily_load_profile

    def _event_activate_energy(self, daily_load_profile):
        """
        Reads the power profile data and calculates the required energy
        for each slot.
        """
        self.load_profile = read_arbitrary_profile(
            InputProfileTypes.POWER,
            daily_load_profile)

    def _update_energy_requirement_future_markets(self):
        """
        Update required energy values for each market slot.
        :return: None
        """
        for market in self.area.all_markets:
            slot_time = market.time_slot
            if not self.load_profile:
                raise D3AException(
                    f"Load {self.owner.name} tries to set its energy forecasted requirement "
                    f"without a profile.")
            load_energy_kWh = \
                find_object_of_same_weekday_and_time(self.load_profile, slot_time)
            self.state.set_desired_energy(load_energy_kWh * 1000, slot_time, overwrite=False)
            self.state.update_total_demanded_energy(slot_time)

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

    def area_reconfigure_event(self, **kwargs):
        self._area_reconfigure_prices(**kwargs)
        if key_in_dict_and_not_none(kwargs, 'daily_load_profile'):
            self._event_activate_energy(kwargs['daily_load_profile'])
