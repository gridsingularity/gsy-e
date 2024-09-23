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
from pendulum import duration

from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.energy_parameters.load import DefinedLoadEnergyParameters


class DefinedLoadStrategy(LoadHoursStrategy):
    """
    Strategy for creating a load profile. It accepts as an input a load csv file or a
    dictionary that contains the load values for each time point
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        daily_load_profile=None,
        fit_to_limit=True,
        energy_rate_increase_per_update=None,
        update_interval=None,
        initial_buying_rate: Union[
            float, dict, str
        ] = ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
        final_buying_rate: Union[
            float, dict, str
        ] = ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
        balancing_energy_ratio: tuple = (
            ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
            ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO,
        ),
        use_market_maker_rate: bool = False,
        daily_load_profile_uuid: str = None,
        daily_load_measurement_uuid: str = None,
        **kwargs
    ):
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
        if kwargs.get("linear_pricing") is not None:
            fit_to_limit = kwargs.get("linear_pricing")

        if update_interval is None:
            update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL
            )

        super().__init__(
            avg_power_W=0,
            hrs_of_day=list(range(0, 24)),
            fit_to_limit=fit_to_limit,
            energy_rate_increase_per_update=energy_rate_increase_per_update,
            update_interval=update_interval,
            final_buying_rate=final_buying_rate,
            initial_buying_rate=initial_buying_rate,
            balancing_energy_ratio=balancing_energy_ratio,
            use_market_maker_rate=use_market_maker_rate,
        )
        self._energy_params = DefinedLoadEnergyParameters(
            daily_load_profile, daily_load_profile_uuid, daily_load_measurement_uuid
        )

        # needed for profile_handler
        self.daily_load_profile_uuid = daily_load_profile_uuid
        self.daily_load_measurement_uuid = daily_load_measurement_uuid

    def event_market_cycle(self):
        self._energy_params.read_and_rotate_profiles()
        super().event_market_cycle()

    def _update_energy_requirement_spot_market(self):
        """
        Update required energy values for each market slot.
        :return: None
        """
        self._energy_params.read_and_rotate_profiles()

        slot_time = self.area.spot_market.time_slot
        self._energy_params.update_energy_requirement(slot_time)

        self._update_energy_requirement_future_markets()

    def _update_energy_requirement_future_markets(self):
        """Update energy requirements in the future markets."""
        for time_slot in self.area.future_market_time_slots:
            self._energy_params.update_energy_requirement(time_slot)

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._area_reconfigure_prices(**kwargs)
        self._energy_params.reset(self.area.spot_market.time_slot, **kwargs)
