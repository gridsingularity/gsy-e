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
from collections import defaultdict
from logging import getLogger
from typing import TYPE_CHECKING, List, Optional

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.utils import key_in_dict_and_not_none
from numpy.random import random
from pendulum import DateTime

from gsy_e.models.area.area_base import AreaBase
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.external_strategies import ExternalMixin
from gsy_e.models.strategy.scm import SCMStrategy

log = getLogger(__name__)

if TYPE_CHECKING:
    from gsy_e.models.area.scm_manager import SCMManager


class CoefficientAreaException(Exception):
    """Exception that is raised when serializing an area."""


class CoefficientArea(AreaBase):
    """Area class for the coefficient matching mechanism."""
    # pytest: disable=too-many-instance-attributes
    def __init__(self, name: str = None, children: List["CoefficientArea"] = None,
                 uuid: str = None,
                 strategy: SCMStrategy = None,
                 config: SimulationConfig = None,
                 grid_fee_percentage: float = None,
                 grid_import_fee_const: float = None,
                 grid_export_fee_const: float = None,
                 coefficient_percentage: float = 0.0,
                 taxes_surcharges: float = 0.0,
                 fixed_monthly_fee: float = 0.0,
                 marketplace_monthly_fee: float = 0.0,
                 assistance_monthly_fee: float = 0.0,
                 market_maker_rate: float = (
                         ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE / 100.),
                 feed_in_tariff: float = GlobalConfig.FEED_IN_TARIFF / 100.,
                 ):
        # pylint: disable=too-many-arguments
        super().__init__(name, children, uuid, strategy, config, grid_fee_percentage)
        self.display_type = (
            "CoefficientArea" if self.strategy is None else self.strategy.__class__.__name__)
        self.validate_coefficient_area_setting(grid_import_fee_const, "grid_import_fee_const")
        self.coefficient_percentage = self.validate_coefficient_area_setting(
            coefficient_percentage, "coefficient_percentage")
        self._taxes_surcharges = self.validate_coefficient_area_setting(
            taxes_surcharges, "taxes_surcharges")
        self._fixed_monthly_fee = self.validate_coefficient_area_setting(
            fixed_monthly_fee, "fixed_monthly_fee")
        self._marketplace_monthly_fee = self.validate_coefficient_area_setting(
            marketplace_monthly_fee, "marketplace_monthly_fee")
        self._assistance_monthly_fee = self.validate_coefficient_area_setting(
            assistance_monthly_fee, "assistance_monthly_fee")
        self._market_maker_rate = self.validate_coefficient_area_setting(
            market_maker_rate, "market_maker_rate")
        self._feed_in_tariff = self.validate_coefficient_area_setting(
            feed_in_tariff, "feed_in_tariff")
        self.past_market_time_slot = None

        self.grid_import_fee_const = grid_import_fee_const
        self.grid_export_fee_const = grid_export_fee_const

    def activate_energy_parameters(self, current_time_slot: DateTime) -> None:
        """Activate the coefficient-based area parameters."""
        self.current_market_time_slot = current_time_slot

        if self.strategy:
            self.strategy.owner = self
            self.strategy.activate(self)
        for child in self.children:
            child.activate_energy_parameters(current_time_slot)

    def cycle_coefficients_trading(self, current_time_slot: DateTime) -> None:
        """Perform operations that should be executed on coefficients trading cycle."""
        self.past_market_time_slot = self.current_market_time_slot
        self.current_market_time_slot = current_time_slot

        if self.strategy:
            self.strategy.market_cycle(self)

        for child in self.children:
            child.cycle_coefficients_trading(current_time_slot)

    def validate_coefficient_area_setting(
            self, setting: Optional[float], setting_name: str) -> float:
        """Check if coefficient area that is not an asset provided SCM setting."""
        if self._is_home_area() and setting is None:
            raise CoefficientAreaException(
                f"In SCM simulations {setting_name} can not be None.")
        return setting

    def area_reconfigure_event(self, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        if self.strategy is not None:
            self.strategy.area_reconfigure_event(**kwargs)
            return True

        if key_in_dict_and_not_none(kwargs, "coefficient_percentage"):
            self.coefficient_percentage = self.validate_coefficient_area_setting(
                kwargs["coefficient_percentage"], "coefficient_percentage")
        if key_in_dict_and_not_none(kwargs, "taxes_surcharges"):
            self._taxes_surcharges = self.validate_coefficient_area_setting(
                kwargs["taxes_surcharges"], "taxes_surcharges")
        if key_in_dict_and_not_none(kwargs, "fixed_monthly_fee"):
            self._fixed_monthly_fee = self.validate_coefficient_area_setting(
                kwargs["fixed_monthly_fee"], "fixed_monthly_fee")
        if key_in_dict_and_not_none(kwargs, "marketplace_monthly_fee"):
            self._marketplace_monthly_fee = self.validate_coefficient_area_setting(
                kwargs["marketplace_monthly_fee"], "marketplace_monthly_fee")
        if key_in_dict_and_not_none(kwargs, "market_maker_rate"):
            self._market_maker_rate = self.validate_coefficient_area_setting(
                kwargs["market_maker_rate"], "market_maker_rate")
        if key_in_dict_and_not_none(kwargs, "feed_in_tariff"):
            self._feed_in_tariff = self.validate_coefficient_area_setting(
                kwargs["feed_in_tariff"], "feed_in_tariff")

    def _is_home_area(self):
        return self.children and all(child.strategy for child in self.children)

    def _calculate_home_after_meter_data(
            self, current_time_slot: DateTime, scm_manager: "SCMManager") -> None:
        home_production_kWh = 0
        home_consumption_kWh = 0

        asset_energy_requirements_kWh = defaultdict(lambda: 0)

        for child in self.children:
            # import
            consumption_kWh = child.strategy.get_energy_to_buy_kWh(current_time_slot)
            asset_energy_requirements_kWh[child.uuid] += consumption_kWh
            home_consumption_kWh += consumption_kWh
            # export
            production_kWh = child.strategy.get_energy_to_sell_kWh(current_time_slot)
            asset_energy_requirements_kWh[child.uuid] -= production_kWh
            home_production_kWh += production_kWh

        scm_manager.add_home_data(
            self.uuid, self.name, self.grid_export_fee_const, self.grid_import_fee_const,
            self.coefficient_percentage,
            self._taxes_surcharges, self._fixed_monthly_fee, self._marketplace_monthly_fee,
            self._assistance_monthly_fee, self._market_maker_rate, self._feed_in_tariff,
            home_production_kWh, home_consumption_kWh, dict(asset_energy_requirements_kWh))

    def calculate_home_after_meter_data(
            self, current_time_slot: DateTime, scm_manager: "SCMManager") -> None:
        """Recursive function that calculates the home after meter data."""
        if self._is_home_area():
            self._calculate_home_after_meter_data(current_time_slot, scm_manager)
        for child in sorted(self.children, key=lambda _: random()):
            child.calculate_home_after_meter_data(current_time_slot, scm_manager)

    def trigger_energy_trades(self, scm_manager: "SCMManager") -> None:
        """Recursive function that triggers energy trading on all children of the root area."""
        if self._is_home_area():
            scm_manager.calculate_home_energy_bills(self.uuid)
        for child in sorted(self.children, key=lambda _: random()):
            child.trigger_energy_trades(scm_manager)

    @property
    def market_maker_rate(self) -> float:
        """Get the market maker rate."""
        return self._market_maker_rate

    def _change_home_coefficient_percentage(self, scm_manager: "SCMManager") -> None:
        community_total_energy_need = scm_manager.community_data.energy_need_kWh
        home_energy_need = scm_manager.get_home_energy_need(self.uuid)
        if community_total_energy_need != 0:
            self.coefficient_percentage = home_energy_need / community_total_energy_need

    def change_home_coefficient_percentage(self, scm_manager: "SCMManager") -> None:
        """Recursive function that change home coefficient percentage based on energy need.
        This method is for dynamic energy allocation algorithm.
        """
        if self._is_home_area():
            self._change_home_coefficient_percentage(scm_manager)
        for child in self.children:
            child.change_home_coefficient_percentage(scm_manager)

    def _consume_commands_from_aggregator(self):
        if self.strategy and getattr(self.strategy, "is_aggregator_controlled", False):
            self.strategy.redis.aggregator.consume_all_area_commands(
                self.uuid, self.strategy.trigger_aggregator_commands)

    def market_cycle_external(self):
        """Method that deals with external requests/commands from aggregators"""
        self._consume_commands_from_aggregator()
        for child in self.children:
            child.market_cycle_external()

    def publish_market_cycle_to_external_clients(self):
        """Recursively notify children and external clients about the market cycle event."""
        if self.strategy and isinstance(self.strategy, ExternalMixin):
            self.strategy.publish_market_cycle()
        for child in self.children:
            child.publish_market_cycle_to_external_clients()
