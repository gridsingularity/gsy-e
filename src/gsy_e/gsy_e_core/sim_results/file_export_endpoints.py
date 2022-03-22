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
from abc import ABC, abstractmethod
from typing import List, Dict

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import BidOfferMatchAlgoEnum, SpotMarketTypeEnum

from gsy_e.gsy_e_core.myco_singleton import bid_offer_matcher
from gsy_e.models.area import Area
from gsy_e.models.market.market_structures import AvailableMarketTypes
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy


class BaseDataExporter(ABC):

    @property
    @abstractmethod
    def labels(self) -> List:
        """Labels for csv headers."""

    @property
    @abstractmethod
    def rows(self) -> List:
        """Return rows containing the offer, bids, trades data."""


class UpperLevelDataExporter(BaseDataExporter):
    def __init__(self, past_markets):
        self.past_markets = past_markets

    @property
    def labels(self) -> List:
        return ["slot",
                "avg trade rate [ct./kWh]",
                "min trade rate [ct./kWh]",
                "max trade rate [ct./kWh]",
                "# trades",
                "total energy traded [kWh]",
                "total trade volume [EURO ct.]"]

    @property
    def rows(self):
        return [self._row(m.time_slot, m) for m in self.past_markets]

    def _row(self, slot, market):
        return [slot,
                market.avg_trade_price,
                market.min_trade_price,
                market.max_trade_price,
                len(market.trades),
                sum(trade.traded_energy for trade in market.trades),
                sum(trade.trade_price for trade in market.trades)]


class FutureMarketsDataExporter(BaseDataExporter):
    def __init__(self, future_markets):
        self.future_markets = future_markets

    @property
    def labels(self) -> List:
        return ["slot",
                "# trades",
                "total energy traded [kWh]",
                "total trade volume [EURO ct.]"]

    @property
    def rows(self):
        if not self.future_markets.market_time_slots:
            return []
        time_slot = self.future_markets.market_time_slots[0]
        return [self._row(time_slot)]

    def _row(self, slot):
        trades = self.future_markets.slot_trade_mapping[slot]
        return [slot,
                len(trades),
                sum(trade.traded_energy for trade in trades),
                sum(trade.trade_price for trade in trades)]


class BalancingDataExporter(BaseDataExporter):
    def __init__(self, past_markets):
        self.past_markets = past_markets

    @property
    def labels(self) -> List:
        return ["slot",
                "avg supply balancing trade rate [ct./kWh]",
                "avg demand balancing trade rate [ct./kWh]"]

    @property
    def rows(self):
        return [self._row(m.time_slot, m) for m in self.past_markets]

    def _row(self, slot, market):
        return [slot,
                market.avg_supply_balancing_trade_rate,
                market.avg_demand_balancing_trade_rate]


class LeafDataExporter(BaseDataExporter):
    def __init__(self, area, past_markets):
        self.area = area
        self.past_markets = past_markets

    @property
    def labels(self) -> List:
        return ["slot",
                "energy traded [kWh]",
                ] + self._specific_labels()

    def _specific_labels(self):
        if isinstance(self.area.strategy, StorageStrategy):
            return ["bought [kWh]", "sold [kWh]", "charge [kWh]", "offered [kWh]", "charge [%]"]
        elif isinstance(self.area.strategy, LoadHoursStrategy):
            return ["desired energy [kWh]", "deficit [kWh]"]
        elif isinstance(self.area.strategy, PVStrategy):
            return ["produced [kWh]", "not sold [kWh]"]
        return []

    @property
    def rows(self):
        return [self._row(market.time_slot, market) for market in self.past_markets]

    def _traded(self, market):
        return (market.traded_energy[self.area.name]
                if self.area.name in market.traded_energy else 0)

    def _row(self, slot, market):
        return [slot,
                self._traded(market),
                ] + self._specific_row(slot, market)

    def _specific_row(self, slot, market):
        if isinstance(self.area.strategy, StorageStrategy):
            s = self.area.strategy.state
            return [market.bought_energy(self.area.name),
                    market.sold_energy(self.area.name),
                    s.charge_history_kWh[slot],
                    s.offered_history[slot],
                    s.charge_history[slot]]
        elif isinstance(self.area.strategy, (LoadHoursStrategy)):
            desired = self.area.strategy.state.get_desired_energy_Wh(slot) / 1000
            return [desired, self._traded(market) + desired]
        elif isinstance(self.area.strategy, PVStrategy):
            not_sold = self.area.strategy.state.get_available_energy_kWh(slot)
            produced = self.area.strategy.state.get_energy_production_forecast_kWh(slot, 0.0)
            return [produced, not_sold]
        return []


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
            return (UpperLevelDataExporter(area.past_markets)
                    if len(area.children) > 0
                    else LeafDataExporter(area, area.parent.past_markets))
        if past_market_type == AvailableMarketTypes.BALANCING:
            return BalancingDataExporter(area.past_balancing_markets)
        if past_market_type == AvailableMarketTypes.SETTLEMENT:
            return (UpperLevelDataExporter(area.past_settlement_markets.values())
                    if len(area.children) > 0
                    else LeafDataExporter(area, area.parent.past_settlement_markets.values()))
        if past_market_type == AvailableMarketTypes.FUTURE and area.future_markets:
            return FutureMarketsDataExporter(area.future_markets)

    def _get_stats_from_market_data(self, out_dict: Dict, area: Area,
                                    past_market_type: AvailableMarketTypes) -> None:
        """Get statistics and write them to out_dict."""
        data = self.export_data_factory(area, past_market_type)
        if area.slug not in out_dict:
            out_dict[area.slug] = dict((label, []) for label in data.labels)
        for row in data.rows:
            for ii, label in enumerate(data.labels):
                out_dict[area.slug][label].append(row[ii])

    def _populate_plots_stats_for_supply_demand_curve(self, area: Area) -> None:
        if (ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.TWO_SIDED.value and
                ConstSettings.MASettings.BID_OFFER_MATCH_TYPE ==
                BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value):
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
            self.cumulative_offers[area.slug][market.time_slot] = (
                clearing_state.cumulative_offers.get(market.id, {}))
            self.cumulative_bids[area.slug][market.time_slot] = (
                clearing_state.cumulative_bids.get(market.id, {}))
            self.clearing[area.slug][market.time_slot] = (
                clearing_state.clearing.get(market.id, ()))

    def _update_plot_stats(self, area: Area) -> None:
        """Populate the statistics for the plots into self.plot_stats."""
        self._get_stats_from_market_data(self.plot_stats, area, AvailableMarketTypes.SPOT)
        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self._get_stats_from_market_data(self.plot_balancing_stats, area,
                                             AvailableMarketTypes.BALANCING)
        if ConstSettings.GeneralSettings.EXPORT_SUPPLY_DEMAND_PLOTS:
            self._populate_plots_stats_for_supply_demand_curve(area)
