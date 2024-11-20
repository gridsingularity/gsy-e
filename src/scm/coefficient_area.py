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

from logging import getLogger
from typing import TYPE_CHECKING, List, Dict

from numpy.random import random
from pendulum import DateTime

from gsy_e.gsy_e_core.util import get_slots_per_month
from gsy_e.models.area.area_base import AreaBase
from scm.scm_dataclasses import SCMAreaProperties
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.external_strategies import ExternalMixin
from scm.strategies import SCMStrategy

log = getLogger(__name__)

if TYPE_CHECKING:
    from scm.scm_manager import SCMManager


class CoefficientAreaException(Exception):
    """Exception that is raised when serializing an area."""


class CoefficientArea(AreaBase):
    """Area class for the coefficient matching mechanism."""

    # pytest: disable=too-many-instance-attributes
    def __init__(
        self,
        name: str = None,
        children: List["CoefficientArea"] = None,
        uuid: str = None,
        strategy: SCMStrategy = None,
        config: SimulationConfig = None,
    ):
        # pylint: disable=too-many-arguments
        super().__init__(name, children, uuid, strategy, config, 0, 0)
        self.display_type = (
            "CoefficientArea" if self.strategy is None else self.strategy.__class__.__name__
        )
        self.past_market_time_slot = None
        self.area_properties = SCMAreaProperties()

    def update_area_properties(self, properties: Dict) -> None:
        """Update area_properties."""
        for property_name, fee_dict in properties.get(self.uuid, {}).items():
            setattr(self.area_properties, property_name, fee_dict)
        try:
            self.area_properties.validate()
        except AssertionError as ex:
            raise CoefficientAreaException(
                f"Invalid fee properties {self.area_properties}"
            ) from ex

    def activate_energy_parameters(self, current_time_slot: DateTime) -> None:
        """Activate the coefficient-based area parameters."""
        self.current_market_time_slot = current_time_slot

        if self.strategy:
            self.strategy.owner = self
            self.strategy.activate(self)
        for child in self.children:
            child.activate_energy_parameters(current_time_slot)

    def _handle_area_parameters_from_profiles(
        self, current_time_slot: DateTime, area_profiles: dict
    ) -> None:
        if self.uuid not in area_profiles:
            return
        area_profile = area_profiles[self.uuid]
        if area_profile.feed_in_tariff:
            self.area_properties.AREA_PROPERTIES["feed_in_tariff"] = area_profile.feed_in_tariff
        if area_profile.utility_rate:
            self.area_properties.AREA_PROPERTIES["market_maker_rate"] = area_profile.utility_rate
        if area_profile.energy_fee:
            self.area_properties.GRID_FEES["grid_import_fee_const"] = area_profile.energy_fee
        if area_profile.energy_cargo_fee:
            self.area_properties.PER_KWH_FEES["energy_cargo_fee"] = area_profile.energy_cargo_fee
        if area_profile.power_fee:
            self.area_properties.MONTHLY_FEES["power_fee"] = (
                area_profile.power_fee
                * area_profile.contracted_power_kw
                / get_slots_per_month(current_time_slot)
            )
        if area_profile.power_cargo_fee:
            self.area_properties.MONTHLY_FEES["power_cargo_fee"] = (
                area_profile.power_cargo_fee
                * area_profile.contracted_power_kw
                / get_slots_per_month(current_time_slot)
            )

    def cycle_coefficients_trading(self, current_time_slot: DateTime, area_profiles: dict) -> None:
        """Perform operations that should be executed on coefficients trading cycle."""
        self.past_market_time_slot = self.current_market_time_slot
        self.current_market_time_slot = current_time_slot

        self._handle_area_parameters_from_profiles(current_time_slot, area_profiles)
        if self.strategy:
            self.strategy.market_cycle(self)

        for child in self.children:
            child.cycle_coefficients_trading(current_time_slot, area_profiles)

    def area_reconfigure_event(self, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        if self.strategy is not None:
            self.strategy.area_reconfigure_event(**kwargs)

    def _calculate_home_after_meter_data(
        self, current_time_slot: DateTime, scm_manager: "SCMManager"
    ) -> None:
        home_production_kWh = 0
        home_consumption_kWh = 0

        for child in self.children:
            # import
            home_consumption_kWh += child.strategy.get_energy_to_buy_kWh(current_time_slot)
            # export
            home_production_kWh += child.strategy.get_energy_to_sell_kWh(current_time_slot)

        scm_manager.add_home_data(
            self.uuid,
            self.name,
            self.area_properties,
            home_production_kWh,
            home_consumption_kWh,
        )

    def aggregate_production_from_all_homes(self, current_time_slot: DateTime) -> float:
        """Aggregate energy production from all homes, in kWh."""
        if self.is_home_area:
            return sum(
                child.strategy.get_energy_to_sell_kWh(current_time_slot) for child in self.children
            )
        return sum(
            child.aggregate_production_from_all_homes(current_time_slot)
            for child in sorted(self.children, key=lambda _: random())
        )

    def calculate_home_after_meter_data_for_collective_self_consumption(
        self,
        current_time_slot: DateTime,
        scm_manager: "SCMManager",
        community_production_kwh: float,
    ):
        """Recursive function that calculates the home after meter data."""
        if self.is_home_area:
            home_consumption_kwh = sum(
                child.strategy.get_energy_to_buy_kWh(current_time_slot) for child in self.children
            )
            home_production_kwh = (
                community_production_kwh
                * self.area_properties.AREA_PROPERTIES["coefficient_percentage"]
            )
            scm_manager.add_home_data(
                self.uuid,
                self.name,
                self.area_properties,
                home_production_kwh,
                home_consumption_kwh,
            )
        for child in sorted(self.children, key=lambda _: random()):
            child.calculate_home_after_meter_data_for_collective_self_consumption(
                current_time_slot, scm_manager, community_production_kwh
            )

    def calculate_home_after_meter_data(
        self, current_time_slot: DateTime, scm_manager: "SCMManager"
    ) -> None:
        """Recursive function that calculates the home after meter data."""
        if self.is_home_area:
            self._calculate_home_after_meter_data(current_time_slot, scm_manager)
        for child in sorted(self.children, key=lambda _: random()):
            child.calculate_home_after_meter_data(current_time_slot, scm_manager)

    def trigger_energy_trades(self, scm_manager: "SCMManager") -> None:
        """Recursive function that triggers energy trading on all children of the root area."""
        if self.is_home_area:
            scm_manager.calculate_home_energy_bills(self.uuid)
        for child in sorted(self.children, key=lambda _: random()):
            child.trigger_energy_trades(scm_manager)

    @property
    def market_maker_rate(self) -> float:
        """Get the market maker rate."""
        return self.area_properties.AREA_PROPERTIES["market_maker_rate"]

    def _change_home_coefficient_percentage(self, scm_manager: "SCMManager") -> None:
        community_total_energy_need = scm_manager.community_data.energy_need_kWh
        home_energy_need = scm_manager.get_home_energy_need(self.uuid)
        if community_total_energy_need != 0:
            self.area_properties.AREA_PROPERTIES["coefficient_percentage"] = (
                home_energy_need / community_total_energy_need
            )

    def change_home_coefficient_percentage(self, scm_manager: "SCMManager") -> None:
        """Recursive function that change home coefficient percentage based on energy need.
        This method is for dynamic energy allocation algorithm.
        """
        if self.is_home_area:
            self._change_home_coefficient_percentage(scm_manager)
        for child in self.children:
            child.change_home_coefficient_percentage(scm_manager)

    def _consume_commands_from_aggregator(self):
        if self.strategy and getattr(self.strategy, "is_aggregator_controlled", False):
            self.strategy.redis.aggregator.consume_all_area_commands(
                self.uuid, self.strategy.trigger_aggregator_commands
            )

    def market_cycle_external(self):
        """External market cycle method."""
        self._consume_commands_from_aggregator()
        for child in self.children:
            child.market_cycle_external()

    def publish_market_cycle_to_external_clients(self):
        """Recursively notify children and external clients about the market cycle event."""
        if self.strategy and isinstance(self.strategy, ExternalMixin):
            self.strategy.publish_market_cycle()
        for child in self.children:
            child.publish_market_cycle_to_external_clients()
