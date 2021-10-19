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

from d3a_interface.constants_limits import ConstSettings
from d3a_interface.read_user_profile import InputProfileTypes
from d3a_interface.utils import key_in_dict_and_not_none, find_object_of_same_weekday_and_time
from pendulum import duration

from d3a.d3a_core.exceptions import D3AException
from d3a.d3a_core.global_objects_singleton import global_objects
from d3a.d3a_core.util import should_read_profile_from_db
from d3a.models.strategy.load_hours import LoadHoursStrategy


class DefinedLoadStrategy(LoadHoursStrategy):
    """
        Strategy for creating a load profile. It accepts as an input a load csv file or a
        dictionary that contains the load values for each time point
    """
    parameters = ("daily_load_profile", "fit_to_limit", "energy_rate_increase_per_update",
                  "update_interval", "initial_buying_rate", "final_buying_rate",
                  "balancing_energy_ratio", "use_market_maker_rate", "daily_load_profile_uuid")

    def __init__(self, daily_load_profile=None,
                 fit_to_limit=True, energy_rate_increase_per_update=None,
                 update_interval=None,
                 initial_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
                 final_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
                 balancing_energy_ratio: tuple =
                 (ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
                  ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO),
                 use_market_maker_rate: bool = False,
                 daily_load_profile_uuid: str = None):
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

        self.profile_uuid = daily_load_profile_uuid
        self._load_profile_W = None
        self._load_profile_kWh = {}

        if should_read_profile_from_db(daily_load_profile_uuid):
            self._load_profile_input = None
        else:
            self._load_profile_input = daily_load_profile

    def _read_or_rotate_profiles(self, reconfigure=False):
        input_profile = self._load_profile_input \
            if reconfigure or not self._load_profile_W else self._load_profile_W

        if global_objects.profiles_handler.should_create_profile(
                self._load_profile_kWh) or reconfigure:
            self._load_profile_kWh = (
                global_objects.profiles_handler.rotate_profile(
                    profile_type=InputProfileTypes.POWER,
                    profile=input_profile,
                    profile_uuid=self.profile_uuid))

    def event_activate_energy(self):
        """
        Runs on activate event.
        :return: None
        """
        self._read_or_rotate_profiles()
        super().event_activate_energy()

    def event_market_cycle(self):
        self._read_or_rotate_profiles()
        super().event_market_cycle()

    def _update_energy_requirement_future_markets(self):
        """
        Update required energy values for each market slot.
        :return: None
        """
        self._read_or_rotate_profiles()

        slot_time = self.area.spot_market.time_slot
        if not self._load_profile_kWh:
            raise D3AException(
                f"Load {self.owner.name} tries to set its energy forecasted requirement "
                f"without a profile.")
        load_energy_kWh = \
            find_object_of_same_weekday_and_time(self._load_profile_kWh, slot_time)
        self.state.set_desired_energy(load_energy_kWh * 1000, slot_time, overwrite=False)
        self.state.update_total_demanded_energy(slot_time)

    def _operating_hours(self, energy_kWh):
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
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._area_reconfigure_prices(**kwargs)
        if key_in_dict_and_not_none(kwargs, "daily_load_profile"):
            self._load_profile_input = kwargs["daily_load_profile"]
            self._read_or_rotate_profiles(reconfigure=True)
