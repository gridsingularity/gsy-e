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

from gsy_framework.constants_limits import ConstSettings
from pendulum import duration

from gsy_e.models.strategy.energy_parameters.pv import (
    PVPredefinedEnergyParameters,
    PVUserProfileEnergyParameters,
)
from gsy_e.models.strategy.pv import PVStrategy


class PVPredefinedStrategy(PVStrategy):
    """
    Strategy responsible for using one of the predefined PV profiles.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        panel_count: int = 1,
        initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
        final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
        cloud_coverage: int = None,
        fit_to_limit: bool = True,
        update_interval=None,
        energy_rate_decrease_per_update=None,
        use_market_maker_rate: bool = False,
        capacity_kW: float = None,
        **kwargs
    ):
        """
        Constructor of PVPredefinedStrategy
        Args:
            panel_count: Number of solar panels for this PV plant
            initial_selling_rate: Upper Threshold for PV offers
            final_selling_rate: Lower Threshold for PV offers
            cloud_coverage: cloud conditions.
                                0=sunny,
                                1=partially cloudy,
                                2=cloudy,
                                4=use global profile
                                None=use global cloud_coverage (default)
            fit_to_limit: Linear curve following initial_selling_rate & final_selling_rate
            update_interval: Interval after which PV will update its offer
            energy_rate_decrease_per_update: Slope of PV Offer change per update
            capacity_kW: power rating of the predefined profiles
        """
        if kwargs.get("linear_pricing") is not None:
            fit_to_limit = kwargs.get("linear_pricing")

        if update_interval is None:
            update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL
            )

        super().__init__(
            panel_count=panel_count,
            initial_selling_rate=initial_selling_rate,
            final_selling_rate=final_selling_rate,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval,
            energy_rate_decrease_per_update=energy_rate_decrease_per_update,
            capacity_kW=capacity_kW,
            use_market_maker_rate=use_market_maker_rate,
        )

        self._energy_params = PVPredefinedEnergyParameters(
            panel_count, cloud_coverage, capacity_kW
        )

    def read_config_event(self):
        # this is to trigger to read from self.simulation_config.cloud_coverage:
        self._energy_params.reconfigure(cloud_coverage=None)
        self.set_produced_energy_forecast_in_state(reconfigure=True)

    def set_produced_energy_forecast_in_state(self, reconfigure=True):
        """Update the production energy forecast."""
        time_slots = [self.area.spot_market.time_slot]
        if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS:
            time_slots.extend(self.area.future_market_time_slots)

        if reconfigure:
            self._energy_params.read_predefined_profile_for_pv(self.simulation_config)

        self._energy_params.set_produced_energy_forecast_in_state(
            self.owner.name, time_slots, reconfigure
        )

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._energy_params.reconfigure(**kwargs)
        self._energy_params.read_predefined_profile_for_pv(self.simulation_config)
        super().area_reconfigure_event(**kwargs)


class PVUserProfileStrategy(PVStrategy):
    """
    Strategy responsible for reading a profile in the form of a dict of values.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        power_profile=None,
        panel_count: int = 1,
        initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
        final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
        fit_to_limit: bool = True,
        update_interval=duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
        energy_rate_decrease_per_update=None,
        use_market_maker_rate: bool = False,
        power_profile_uuid: str = None,
        power_measurement_uuid: str = None,
        **kwargs
    ):
        """
        Constructor of PVUserProfileStrategy
        Args:
            power_profile: input profile for a day. Can be either a csv file path,
                           or a dict with hourly data (Dict[int, float])
                           or a dict with arbitrary time data (Dict[str, float])
            panel_count: number of solar panels for this PV plant
            final_selling_rate: lower threshold for the PV sale price
        """
        if kwargs.get("linear_pricing") is not None:
            fit_to_limit = kwargs.get("linear_pricing")

        super().__init__(
            panel_count=panel_count,
            initial_selling_rate=initial_selling_rate,
            final_selling_rate=final_selling_rate,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval,
            energy_rate_decrease_per_update=energy_rate_decrease_per_update,
            use_market_maker_rate=use_market_maker_rate,
        )
        self._energy_params = PVUserProfileEnergyParameters(
            panel_count, power_profile, power_profile_uuid, power_measurement_uuid
        )

        # needed for profile_handler
        self.power_profile_uuid = power_profile_uuid
        self.power_measurement_uuid = power_measurement_uuid

    def set_produced_energy_forecast_in_state(self, reconfigure=True):
        time_slots = [self.area.spot_market.time_slot]
        if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS:
            time_slots.extend(self.area.future_market_time_slots)

        self._energy_params.set_produced_energy_forecast_in_state(
            self.owner.name, time_slots, reconfigure
        )

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        super().area_reconfigure_event(**kwargs)
        self._energy_params.reset(**kwargs)
        self.set_produced_energy_forecast_in_state(reconfigure=True)

    def event_market_cycle(self):
        self._energy_params.read_predefined_profile_for_pv()
        super().event_market_cycle()

    def event_activate_energy(self):
        self._energy_params.read_predefined_profile_for_pv()
        super().event_activate_energy()
