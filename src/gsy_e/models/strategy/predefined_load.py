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
from typing import Union

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.utils import find_object_of_same_weekday_and_time
from pendulum import duration, DateTime

from gsy_e.gsy_e_core.exceptions import GSyException
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.util import should_read_profile_from_db
from gsy_e.models.state import LoadState
from gsy_e.models.strategy.load_hours import LoadHoursStrategy, LoadHoursPerDayEnergyParameters


class DefinedLoadEnergyParameters(LoadHoursPerDayEnergyParameters):
    """Energy parameters for the defined load strategy class."""
    def __init__(self, daily_load_profile=None, daily_load_profile_uuid: str = None):
        super().__init__(avg_power_W=0, hrs_per_day=24, hrs_of_day=list(range(0, 24)))
        self.profile_uuid = daily_load_profile_uuid
        self._load_profile_W = None
        self._load_profile_kWh = {}
        self.state = LoadState()

        if should_read_profile_from_db(daily_load_profile_uuid):
            self._load_profile_input = None
        else:
            self._load_profile_input = daily_load_profile

    def serialize(self):
        return {
            "daily_load_profile": self._load_profile_input,
            "daily_load_profile_uuid": self.profile_uuid
        }

    def event_activate_energy(self, area):
        """
        Runs on activate event.
        :return: None
        """
        self.read_or_rotate_profiles()
        super().event_activate_energy(area)

    def reset(self, time_slot: DateTime, **kwargs) -> None:
        if kwargs.get("daily_load_profile") is not None:
            self._load_profile_input = kwargs["daily_load_profile"]
            self.read_or_rotate_profiles(reconfigure=True)

    def read_or_rotate_profiles(self, reconfigure=False):
        """Read power profiles or rotate them, from the DB or from JSON dicts."""
        input_profile = (self._load_profile_input
                         if reconfigure or not self._load_profile_W
                         else self._load_profile_W)

        if global_objects.profiles_handler.should_create_profile(
                self._load_profile_kWh) or reconfigure:
            self._load_profile_kWh = (
                global_objects.profiles_handler.rotate_profile(
                    profile_type=InputProfileTypes.POWER,
                    profile=input_profile,
                    profile_uuid=self.profile_uuid))

    def update_energy_requirement(self, time_slot, overwrite=False):
        if not self._load_profile_kWh:
            raise GSyException(
                "Load tries to set its energy forecasted requirement "
                "without a profile.")
        load_energy_kwh = find_object_of_same_weekday_and_time(self._load_profile_kWh, time_slot)
        self.state.set_desired_energy(load_energy_kwh * 1000, time_slot, overwrite=False)
        self.state.update_total_demanded_energy(time_slot)

    def _operating_hours(self, energy_kWh):
        """
        Disabled feature for this subclass
        """
        return 0

    def allowed_operating_hours(self, time_slot):
        """
        Disabled feature for this subclass
        """
        return True


class DefinedLoadStrategy(LoadHoursStrategy):
    """
        Strategy for creating a load profile. It accepts as an input a load csv file or a
        dictionary that contains the load values for each time point
    """
    # pylint: disable=too-many-arguments
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

        if not hasattr(self, "_energy_params"):
            self._energy_params = DefinedLoadEnergyParameters(
                daily_load_profile, daily_load_profile_uuid)
        super().__init__(avg_power_W=0, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate)

    def event_market_cycle(self):
        self._energy_params.read_or_rotate_profiles()
        super().event_market_cycle()

    def _update_energy_requirement_spot_market(self):
        """
        Update required energy values for each market slot.
        :return: None
        """
        self._energy_params.read_or_rotate_profiles()

        slot_time = self.area.spot_market.time_slot
        self._energy_params.update_energy_requirement(slot_time, self.owner.name)

        self._update_energy_requirement_future_markets()

    def _update_energy_requirement_future_markets(self):
        """Update energy requirements in the future markets."""
        for time_slot in self.area.future_market_time_slots:
            self._energy_params.update_energy_requirement(time_slot, self.owner.name)

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._area_reconfigure_prices(**kwargs)
        self._energy_params.reset(self.area.spot_market.time_slot, **kwargs)
