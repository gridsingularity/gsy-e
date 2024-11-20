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

from statistics import mean
from typing import TYPE_CHECKING, List

from gsy_framework.enums import AvailableMarketTypes

from gsy_e.gsy_e_core.sim_results.file_export_endpoints import (
    FileExportEndpoints,
    BaseDataExporter,
)
from gsy_e.models.area import Area
from gsy_e.models.strategy.scm.heat_pump import ScmHeatPumpStrategy
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy, SCMLoadProfileStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import CoefficientArea
    from scm.scm_manager import SCMManager


class CoefficientFileExportEndpoints(FileExportEndpoints):
    """FileExportEndpoints for SCm simulations"""

    def __init__(self):
        super().__init__()
        self._scm_manager = None

    def __call__(self, area, scm_manager: "SCMManager" = None):
        self._scm_manager = scm_manager
        super().__call__(area)

    def export_data_factory(
        self, area: "CoefficientArea", past_market_type: AvailableMarketTypes
    ) -> BaseDataExporter:
        """Decide which data acquisition class to use."""
        assert past_market_type == AvailableMarketTypes.SPOT, "SCM supports only spot market."
        return (
            CoefficientDataExporter(area, self._scm_manager)
            if len(area.children) > 0
            else CoefficientLeafDataExporter(area)
        )

    def _update_plot_stats(self, area: Area) -> None:
        """
        Method that calculates the stats for the plots. Should omit the balancing market and
        supply demand plots for the SCM case.
        """
        self._get_stats_from_market_data(self.plot_stats, area, AvailableMarketTypes.SPOT)

    def _populate_plots_stats_for_supply_demand_curve(self, area: Area) -> None:
        """
        Supply demand curve should not be implemented for SCM due to its dependency with 2-sided
        pay as clear algorithm.
        """
        raise NotImplementedError


class CoefficientDataExporter(BaseDataExporter):
    """DataExporter for SCm simulations."""

    def __init__(self, area: "CoefficientArea", scm_manager: "SCMManager" = None):
        self._area = area
        self._scm = scm_manager

    @property
    def labels(self) -> List:
        return [
            "slot",
            "avg trade rate [ct./kWh]",
            "min trade rate [ct./kWh]",
            "max trade rate [ct./kWh]",
            "# trades",
            "total energy traded [kWh]",
            "total trade volume [EURO ct.]",
        ]

    @property
    def rows(self) -> List:

        if not self._scm:
            return []
        area_results = self._scm.get_area_results(self._area.uuid, serializable=False)
        if not area_results["after_meter_data"]:
            return []
        trade_rates = [t.trade_rate for t in area_results["after_meter_data"]["trades"]]
        trade_prices = [t.trade_price for t in area_results["after_meter_data"]["trades"]]
        trades_energy = [t.traded_energy for t in area_results["after_meter_data"]["trades"]]
        return [
            [
                self._area.current_market_time_slot,
                mean(trade_rates) if trade_rates else 0.0,
                min(trade_rates) if trade_rates else 0.0,
                max(trade_rates) if trade_rates else 0.0,
                len(trade_rates) if trade_rates else 0.0,
                sum(trades_energy) if trades_energy else 0.0,
                sum(trade_prices) if trade_prices else 0.0,
            ]
        ]


class CoefficientLeafDataExporter(BaseDataExporter):
    # pylint: disable=protected-access
    """LeafDataExporter for SCM simulations."""

    def __init__(self, area: "CoefficientArea"):
        self._area = area

    @property
    def labels(self) -> List:
        if isinstance(self._area.strategy, SCMStorageStrategy):
            return ["slot", "traded energy [kWh]"]
        if isinstance(self._area.strategy, (SCMLoadHoursStrategy, SCMLoadProfileStrategy)):
            return ["slot", "desired energy [kWh]", "deficit [kWh]"]
        if isinstance(self._area.strategy, SCMPVUserProfile):
            return ["slot", "produced [kWh]", "not sold [kWh]"]
        return []

    @property
    def rows(self):
        slot = self._area.current_market_time_slot
        if slot is None:
            return []
        if isinstance(self._area.strategy, SCMStorageStrategy):
            traded = self._area.strategy._energy_params.energy_profile.profile[slot]
            return [[slot, traded]]
        if isinstance(
            self._area.strategy,
            (SCMLoadHoursStrategy, SCMLoadProfileStrategy, ScmHeatPumpStrategy),
        ):
            desired = self._area.strategy.state.get_desired_energy_Wh(slot) / 1000
            # All energy is traded in SCM
            return [[slot, desired, 0.0]]
        if isinstance(self._area.strategy, SCMPVUserProfile):
            not_sold = self._area.strategy.state.get_available_energy_kWh(slot)
            produced = self._area.strategy.state.get_energy_production_forecast_kWh(slot, 0.0)
            return [[slot, produced, not_sold]]
        return []
