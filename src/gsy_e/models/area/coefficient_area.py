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
from typing import TYPE_CHECKING, List, Optional

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from numpy.random import random
from pendulum import DateTime

from gsy_e.models.area.area_base import AreaBase
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.scm import SCMStrategy

log = getLogger(__name__)

if TYPE_CHECKING:
    from gsy_e.models.area.scm_manager import SCMManager


class CoefficientAreaException(Exception):
    """Exception that is raised when serializing an area."""


def assert_coefficient_area_settings(
        strategy: Optional[SCMStrategy], setting: Optional[float], setting_name: str) -> float:
    """Check if coefficient area that is not an asset provided SCM setting."""
    if strategy is None and setting is None:
        raise CoefficientAreaException(f"In SCM simulations {setting_name} can not be None.")
    return setting


class CoefficientArea(AreaBase):
    """Area class for the coefficient matching mechanism."""
    def __init__(self, name: str = None, children: List["CoefficientArea"] = None,
                 uuid: str = None,
                 strategy: SCMStrategy = None,
                 config: SimulationConfig = None,
                 grid_fee_percentage: float = None,
                 grid_fee_constant: float = None,
                 coefficient_percentage: float = 0.0,
                 taxes_surcharges: float = 0.0,
                 fixed_monthly_fee: float = 0.0,
                 marketplace_monthly_fee: float = 0.0,
                 market_maker_rate: float = (
                         ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE / 100.),
                 feed_in_tariff: float = GlobalConfig.FEED_IN_TARIFF / 100.,
                 ):
        # pylint: disable=too-many-arguments
        assert_coefficient_area_settings(strategy, grid_fee_constant, "grid_fee_constant")
        super().__init__(name, children, uuid, strategy, config, grid_fee_percentage,
                         grid_fee_constant)
        self.display_type = (
            "CoefficientArea" if self.strategy is None else self.strategy.__class__.__name__)
        self.coefficient_percentage = assert_coefficient_area_settings(
            strategy, coefficient_percentage, "coefficient_percentage")
        self._taxes_surcharges = assert_coefficient_area_settings(
            strategy, taxes_surcharges, "taxes_surcharges")
        self._fixed_monthly_fee = assert_coefficient_area_settings(
            strategy, fixed_monthly_fee, "fixed_monthly_fee")
        self._marketplace_monthly_fee = assert_coefficient_area_settings(
            strategy, marketplace_monthly_fee, "marketplace_monthly_fee")
        self._market_maker_rate = assert_coefficient_area_settings(
            strategy, market_maker_rate, "market_maker_rate")
        self._feed_in_tariff = assert_coefficient_area_settings(
            strategy, feed_in_tariff, "feed_in_tariff")
        self.past_market_time_slot = None

    def activate_energy_parameters(self, current_time_slot: DateTime) -> None:
        """Activate the coefficient-based area parameters."""
        self._current_market_time_slot = current_time_slot

        if self.strategy:
            self.strategy.activate(self)
        for child in self.children:
            child.activate_energy_parameters(current_time_slot)

    def cycle_coefficients_trading(self, current_time_slot: DateTime) -> None:
        """Perform operations that should be executed on coefficients trading cycle."""
        self.past_market_time_slot = self._current_market_time_slot
        self._current_market_time_slot = current_time_slot

        if self.strategy:
            self.strategy.market_cycle(self)

        for child in self.children:
            child.cycle_coefficients_trading(current_time_slot)

    def _is_home_area(self):
        return self.children and all(child.strategy for child in self.children)

    def _calculate_home_after_meter_data(
            self, current_time_slot: DateTime, scm_manager: "SCMManager") -> None:
        production_kWh = sum(child.strategy.get_energy_to_sell_kWh(current_time_slot)
                             for child in self.children)
        consumption_kWh = sum(child.strategy.get_energy_to_buy_kWh(current_time_slot)
                              for child in self.children)
        scm_manager.add_home_data(
            self.uuid, self.name, self.grid_fee_constant, self.coefficient_percentage,
            self._taxes_surcharges, self._fixed_monthly_fee, self._marketplace_monthly_fee,
            self._market_maker_rate, self._feed_in_tariff, production_kWh, consumption_kWh)

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
