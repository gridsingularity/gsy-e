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

# pylint: disable=too-many-return-statements, broad-exception-raised
from abc import ABC, abstractmethod
from typing import Dict, List

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes, BidOfferMatchAlgoEnum

from gsy_e.constants import ROUND_TOLERANCE_EXPORT
from gsy_e.gsy_e_core.matching_engine_singleton import bid_offer_matcher
from gsy_e.gsy_e_core.util import is_two_sided_market_simulation
from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.ev_charger import EVChargerStrategy
from gsy_e.models.strategy.heat_pump import (
    HeatPumpStrategy,
    MultipleTankHeatPumpStrategy,
)
from gsy_e.models.strategy.virtual_heatpump import (
    VirtualHeatpumpStrategy,
    MultipleTankVirtualHeatpumpStrategy,
)


def is_heatpump_with_tanks(area: Area):
    """Return if area has a heat pump strategy."""
    return isinstance(
        area.strategy,
        (
            MultipleTankHeatPumpStrategy,
            MultipleTankVirtualHeatpumpStrategy,
            HeatPumpStrategy,
            VirtualHeatpumpStrategy,
        ),
    )


class BaseDataExporter(ABC):
    """Base class for data exporter."""

    @property
    @abstractmethod
    def labels(self) -> List:
        """Labels for csv headers."""

    @property
    @abstractmethod
    def rows(self) -> List:
        """Return rows containing the offer, bids, trades data."""


class UpperLevelDataExporter(BaseDataExporter):
    """Data exporter for areas higher in the grid tree."""

    def __init__(self, past_markets):
        self.past_markets = past_markets

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
    def rows(self):
        return [self._row(m.time_slot, m) for m in self.past_markets]

    @staticmethod
    def _row(slot, market):
        return [
            slot,
            market.avg_trade_price,
            market.min_trade_price,
            market.max_trade_price,
            len(market.trades),
            sum(trade.traded_energy for trade in market.trades),
            sum(trade.trade_price for trade in market.trades),
        ]


class FutureMarketsDataExporter(BaseDataExporter):
    """Data explorer for future market stats."""

    def __init__(self, future_markets):
        self.future_markets = future_markets

    @property
    def labels(self) -> List:
        return ["slot", "# trades", "total energy traded [kWh]", "total trade volume [EURO ct.]"]

    @property
    def rows(self):
        if not self.future_markets.market_time_slots:
            return []
        time_slot = self.future_markets.market_time_slots[0]
        return [self._row(time_slot)]

    def _row(self, slot):
        trades = self.future_markets.slot_trade_mapping[slot]
        return [
            slot,
            len(trades),
            sum(trade.traded_energy for trade in trades),
            sum(trade.trade_price for trade in trades),
        ]


class BalancingDataExporter(BaseDataExporter):
    """Data explorer for balancing market stats."""

    def __init__(self, past_markets):
        self.past_markets = past_markets

    @property
    def labels(self) -> List:
        return [
            "slot",
            "avg supply balancing trade rate [ct./kWh]",
            "avg demand balancing trade rate [ct./kWh]",
        ]

    @property
    def rows(self):
        return [self._row(m.time_slot, m) for m in self.past_markets]

    @staticmethod
    def _row(slot, market):
        return [
            slot,
            market.avg_supply_balancing_trade_rate,
            market.avg_demand_balancing_trade_rate,
        ]


class LeafDataExporter(BaseDataExporter):
    """Data explorer for leaf areas."""

    def __init__(self, area, past_markets):
        self.area = area
        self.past_markets = past_markets

    @property
    def labels(self) -> List:
        return [
            "slot",
            "energy traded [kWh]",
        ] + self._specific_labels()

    def _specific_labels(self):
        if isinstance(self.area.strategy, EVChargerStrategy):
            return [
                "charging-session",
                "bought [kWh]",
                "sold [kWh]",
                "charge [kWh]",
                "offered [kWh]",
                "charge [%], losses[kWh]",
            ]
        if isinstance(self.area.strategy, StorageStrategy):
            return [
                "bought [kWh]",
                "sold [kWh]",
                "charge [kWh]",
                "offered [kWh]",
                "charge [%], losses[kWh]",
            ]
        if isinstance(self.area.strategy, LoadHoursStrategy):
            return ["desired energy [kWh]", "deficit [kWh]"]
        if isinstance(self.area.strategy, PVStrategy):
            return ["produced [kWh]", "not sold [kWh]"]
        return []

    @property
    def rows(self):
        return [self._row(market.time_slot, market) for market in self.past_markets]

    def _traded(self, market):
        return (
            market.traded_energy[self.area.name] if self.area.name in market.traded_energy else 0
        )

    def _row(self, slot, market):
        return [
            slot,
            self._traded(market),
        ] + self._specific_row(slot, market)

    def _specific_row(self, slot, market):
        if isinstance(self.area.strategy, EVChargerStrategy):
            s = self.area.strategy.state

            if s.active_charging_session:
                return [
                    s.active_charging_session.session_id,
                    market.bought_energy(self.area.name),
                    market.sold_energy(self.area.name),
                    s.charge_history_kWh[slot],
                    s.offered_history[slot],
                    s.charge_history[slot],
                    s.loss_history.get(slot, 0),
                ]
            return [
                "EV_NOT_CONNECTED",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
            ]
        if isinstance(self.area.strategy, StorageStrategy):
            s = self.area.strategy.state
            return [
                market.bought_energy(self.area.name),
                market.sold_energy(self.area.name),
                s.charge_history_kWh[slot],
                s.offered_history[slot],
                s.charge_history[slot],
                s.loss_history.get(slot, 0),
            ]
        if isinstance(self.area.strategy, LoadHoursStrategy):
            desired = self.area.strategy.state.get_desired_energy_Wh(slot) / 1000
            return [desired, self._traded(market) + desired]
        if isinstance(self.area.strategy, PVStrategy):
            not_sold = self.area.strategy.state.get_available_energy_kWh(slot)
            produced = self.area.strategy.state.get_energy_production_forecast_kWh(slot, 0.0)
            return [produced, not_sold]
        return []


class HeatPumpDataExporter(BaseDataExporter):
    """Data exporter dedicated to heat pump areas"""

    def __init__(self, area, past_markets):
        assert is_heatpump_with_tanks(area)
        self.area = area
        self.past_markets = past_markets

    @property
    def labels(self) -> Dict[str, List]:
        return {
            "heat_pump": [
                "slot",
                "energy traded [kWh]",
                "COP",
                "heat demand [kJ]",
                "average SOC",
                "average tank temp [C]",
                "storage inlet temperature [C]",
                "net heat consumed [kJ]",
            ],
            "water_tanks": self._water_tank_labels,
            "pcm_tanks": self._pcm_tank_labels,
        }

    @property
    def rows(self) -> Dict[str, List]:
        return {
            "heat_pump": [
                self._row(market.time_slot, market, "heat_pump") for market in self.past_markets
            ],
            "water_tanks": [
                self._row(market.time_slot, market, "water_tanks") for market in self.past_markets
            ],
            "pcm_tanks": [
                self._row(market.time_slot, market, "pcm_tanks") for market in self.past_markets
            ],
        }

    def _traded(self, market):
        return (
            market.traded_energy[self.area.name] if self.area.name in market.traded_energy else 0
        )

    def _row(self, slot, market, file_key):
        rows = [slot]
        if file_key == "heat_pump":
            hp_stats = self.area.strategy.state.get_results_dict(slot)
            rows += [
                round(self._traded(market), ROUND_TOLERANCE_EXPORT),
                round(hp_stats["cop"], ROUND_TOLERANCE_EXPORT),
                round(hp_stats["heat_demand_kJ"], ROUND_TOLERANCE_EXPORT),
                round(hp_stats["average_soc"], ROUND_TOLERANCE_EXPORT),
                round(hp_stats["average_tank_temp_C"], ROUND_TOLERANCE_EXPORT),
                round(hp_stats["average_inlet_temperature_C"], ROUND_TOLERANCE_EXPORT),
                round(hp_stats["net_heat_consumed_kJ"], ROUND_TOLERANCE_EXPORT),
            ]
        if file_key == "water_tanks":
            for tank in self.area.strategy.state.get_results_dict(slot)["tanks"]:
                if tank["type"] == "WATER":
                    rows.append(round(tank["storage_temp_C"], ROUND_TOLERANCE_EXPORT))
                    rows.append(round(tank["soc"], ROUND_TOLERANCE_EXPORT))
        if file_key == "pcm_tanks":
            for tank in self.area.strategy.state.get_results_dict(slot)["tanks"]:
                if tank["type"] == "PCM":
                    rows.append(round(tank["storage_temp_C"], ROUND_TOLERANCE_EXPORT))
                    rows.append(round(tank["soc"], ROUND_TOLERANCE_EXPORT))
        return rows

    @property
    def _water_tank_labels(self):
        labels = ["slot"]
        for number, tank in enumerate(self.area.strategy.state.get_results_dict()["tanks"]):
            if tank["type"] == "WATER":
                tank_name_str = tank["name"] if tank["name"] else f"tank {number + 1}"
                labels.append(f"{tank_name_str} temperature C")
                labels.append(f"{tank_name_str} SOC %")
        if len(labels) == 1:
            # case when no water tank was configured
            return []
        return labels

    @property
    def _pcm_tank_labels(self):
        labels = ["slot"]
        for number, tank in enumerate(self.area.strategy.state.get_results_dict()["tanks"]):
            if tank["type"] == "PCM":
                tank_name_str = tank["name"] if tank["name"] else f"tank {number + 1}"
                labels.append(f"{tank_name_str} temperature C")
                labels.append(f"{tank_name_str} SOC %")
        if len(labels) == 1:
            # case when no PCM tank was configured
            return []
        return labels


class FileExportEndpoints:
    """Handle data preparation for csv-file and plot export."""

    def __init__(self):
        self.plot_stats = {}
        self.plot_balancing_stats = {}
        self.cumulative_offers = {}
        self.cumulative_bids = {}
        self.clearing = {}

    def __call__(self, area):
        self._populate_area_children_data(area)

    def _populate_area_children_data(self, area: Area) -> None:
        """Wrapper for calling self.update_plot_stats recursively"""
        if area.children:
            for child in area.children:
                self._populate_area_children_data(child)
        self._update_plot_stats(area)

    @staticmethod
    def export_data_factory(
        area: Area, past_market_type: AvailableMarketTypes
    ) -> BaseDataExporter:
        """Decide which data acquisition class to use."""
        if past_market_type == AvailableMarketTypes.SPOT:
            if len(area.children) > 0:
                return UpperLevelDataExporter(area.past_markets)
            return (
                HeatPumpDataExporter(area, area.parent.past_markets)
                if is_heatpump_with_tanks(area)
                else LeafDataExporter(area, area.parent.past_markets)
            )
        if past_market_type == AvailableMarketTypes.BALANCING:
            return BalancingDataExporter(area.past_balancing_markets)
        if past_market_type == AvailableMarketTypes.SETTLEMENT:
            return (
                UpperLevelDataExporter(area.past_settlement_markets.values())
                if len(area.children) > 0
                else LeafDataExporter(area, area.parent.past_settlement_markets.values())
            )
        if past_market_type == AvailableMarketTypes.FUTURE and area.future_markets:
            return FutureMarketsDataExporter(area.future_markets)
        raise Exception(
            "past_market_type not compatible"
        )  # pylint: disable=broad-exception-raised

    def _get_stats_from_market_data(
        self, out_dict: Dict, area: Area, past_market_type: AvailableMarketTypes
    ) -> None:
        """Get statistics and write them to out_dict."""
        data = self.export_data_factory(area, past_market_type)
        if area.slug not in out_dict:
            out_dict[area.slug] = dict((label, []) for label in data.labels)
        for row in data.rows:
            for ii, label in enumerate(data.labels):
                out_dict[area.slug][label].append(row[ii])

    def _populate_plots_stats_for_supply_demand_curve(self, area: Area) -> None:
        if (
            is_two_sided_market_simulation()
            and ConstSettings.MASettings.BID_OFFER_MATCH_TYPE
            == BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value
        ):
            if len(area.past_markets) == 0:
                return
            market = area.past_markets[-1]
            if area.slug not in self.cumulative_offers:
                self.cumulative_offers[area.slug] = {}
                self.cumulative_bids[area.slug] = {}
                self.clearing[area.slug] = {}
            if market.time_slot not in self.cumulative_offers[area.slug]:
                self.cumulative_offers[area.slug][market.time_slot] = {}
                self.cumulative_bids[area.slug][market.time_slot] = {}
                self.clearing[area.slug][market.time_slot] = {}
                clearing_state = bid_offer_matcher.matcher.match_algorithm.state

            # pylint: disable=possibly-used-before-assignment
            self.cumulative_offers[area.slug][market.time_slot] = (
                clearing_state.cumulative_offers.get(market.id, {})
            )
            self.cumulative_bids[area.slug][market.time_slot] = clearing_state.cumulative_bids.get(
                market.id, {}
            )
            self.clearing[area.slug][market.time_slot] = clearing_state.clearing.get(market.id, ())

    def _update_plot_stats(self, area: Area) -> None:
        """Populate the statistics for the plots into self.plot_stats."""
        self._get_stats_from_market_data(self.plot_stats, area, AvailableMarketTypes.SPOT)
        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self._get_stats_from_market_data(
                self.plot_balancing_stats, area, AvailableMarketTypes.BALANCING
            )
        if ConstSettings.GeneralSettings.EXPORT_SUPPLY_DEMAND_PLOTS:
            self._populate_plots_stats_for_supply_demand_curve(area)
