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
from copy import copy
from statistics import mean, median
from typing import Dict, List, Optional

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Offer
from gsy_framework.utils import (
    area_name_from_area_or_ma_name, convert_pendulum_to_str_in_dict,
    convert_str_to_pendulum_in_dict)
from gsy_framework.utils import limit_float_precision
from pendulum import DateTime

from gsy_e.gsy_e_core.util import add_or_create_key, area_sells_to_child, child_buys_from_area
from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy

default_trade_stats_dict = {
    "min_trade_rate": None,
    "max_trade_rate": None,
    "avg_trade_rate": None,
    "median_trade_rate": None,
    "total_traded_energy_kWh": None}


class AreaStats:
    """
    Handle tracking and updating for targeted area statistics
    """
    def __init__(self, area_markets, area):
        self._markets = area_markets
        self._area = area
        self.aggregated_stats = {}
        self.market_bills = {}
        self.rate_stats_market = {}
        self.kpi = {}
        self.exported_traded_energy_kwh = {}
        self.imported_traded_energy_kwh = {}
        self.total_energy_deviance_kWh: Dict[DateTime, Dict[str, float]] = {}

    def get_state(self):
        """Get the current area state to be saved in DB and used as reference point for simulation
        restoration from last know state in case of simulation crash"""
        return {
            "rate_stats_market": convert_pendulum_to_str_in_dict(self.rate_stats_market),
            "exported_energy": convert_pendulum_to_str_in_dict(self.exported_traded_energy_kwh),
            "imported_energy": convert_pendulum_to_str_in_dict(self.imported_traded_energy_kwh),
        }

    def restore_state(self, saved_state: Dict) -> None:
        """Restoration of simulation from its last known state"""
        if not saved_state.get("rate_stats_market"):
            return
        self.rate_stats_market.update(
            convert_str_to_pendulum_in_dict(saved_state["rate_stats_market"]))
        self.exported_traded_energy_kwh.update(
            convert_str_to_pendulum_in_dict(saved_state["exported_energy"]))
        self.imported_traded_energy_kwh.update(
            convert_str_to_pendulum_in_dict(saved_state["imported_energy"]))

    def update_aggregated_stats(self, area_stats: Dict) -> None:
        """Update area's aggregated_stats"""
        self.aggregated_stats = area_stats

    def _extract_from_bills(self, trade_key: str) -> Dict:
        if self.current_market is None:
            return {}
        return {key: self.aggregated_stats["bills"][trade_key][key]
                for key in ["earned", "spent", "bought", "sold"]} \
            if "bills" in self.aggregated_stats \
               and trade_key in self.aggregated_stats["bills"] else {}

    def update_area_market_stats(self) -> None:
        """Update Area Market stats"""
        if self.current_market is not None:
            self.market_bills = \
                {self.current_market.time_slot: {
                    "Accumulated Trades": self._extract_from_bills("Accumulated Trades")}}

            self.rate_stats_market = {
                self.current_market.time_slot: self.min_max_avg_median_rate_current_market()
            }
            self._aggregate_exported_imported_energy()

    def get_last_market_bills(self) -> Dict:
        """Get energy bill statistics of last market"""
        return {key.lower().replace(" ", "_"): self._extract_from_bills(key)
                for key in ["Accumulated Trades", "External Trades"]}

    @property
    def cheapest_offers(self) -> List[Offer]:
        """Extract the cheapest offer from the market"""
        cheapest_offers = []
        for market in self._markets.markets.values():
            cheapest_offers.extend(market.sorted_offers[0:1])
        return cheapest_offers

    def _get_current_market_bills(self) -> Dict:
        return self.market_bills.get(self.current_market.time_slot, None)

    def _get_current_market_area_throughput(self) -> Dict:
        return {"import": self.imported_traded_energy_kwh.get(self.current_market.time_slot, None),
                "export": self.exported_traded_energy_kwh.get(self.current_market.time_slot, None)}

    def get_price_stats_current_market(self) -> Optional[Dict]:
        """Get the price and energy traded statistics of current market"""
        return (self.rate_stats_market.get(self.current_market.time_slot, None)
                if self.current_market is not None else None)

    def min_max_avg_median_rate_current_market(self) -> Dict:
        """Get min, max, average & median energy traded rate as well as
        total volume of energy traded"""
        out_dict = copy(default_trade_stats_dict)
        trade_volumes = [trade.traded_energy for trade in self.current_market.trades]
        trade_rates = [trade.trade_rate
                       for trade in self.current_market.trades]
        if len(trade_rates) > 0:
            out_dict["min_trade_rate"] = limit_float_precision(min(trade_rates))
            out_dict["max_trade_rate"] = limit_float_precision(max(trade_rates))
            out_dict["avg_trade_rate"] = limit_float_precision(mean(trade_rates))
            out_dict["median_trade_rate"] = limit_float_precision(median(trade_rates))
            out_dict["total_traded_energy_kWh"] = limit_float_precision(sum(trade_volumes))
        return out_dict

    @property
    def current_market(self) -> MarketBase:
        """Return the current market object"""
        past_markets = list(self._markets.past_markets.values())
        return past_markets[-1] if len(past_markets) > 0 else None

    def get_last_market_stats(self, dso: bool = False) -> Dict:
        """Get statistics of last market"""
        out_dict = {}
        if self.current_market is None:
            return out_dict
        out_dict = copy(self.rate_stats_market.get(self.current_market.time_slot,
                                                   default_trade_stats_dict))
        out_dict["market_bill"] = self._get_current_market_bills()
        out_dict["market_fee_revenue"] = self._area.current_market.market_fee
        if dso:
            out_dict["area_throughput"] = self._get_current_market_area_throughput()
            out_dict["self_sufficiency"] = self.kpi.get("self_sufficiency", None)
            out_dict["self_consumption"] = self.kpi.get("self_consumption", None)
            out_dict["market_energy_deviance"] = self.total_energy_deviance_kWh.get(
                self.current_market.time_slot)

        return out_dict

    def _aggregate_exported_imported_energy(self) -> None:
        if self._area.current_market is None:
            return

        self.imported_traded_energy_kwh = {}
        self.exported_traded_energy_kwh = {}

        child_names = [area_name_from_area_or_ma_name(c.name) for c in self._area.children]
        if getattr(self.current_market, "trades", None) is not None:
            for trade in self.current_market.trades:
                if child_buys_from_area(trade, self._area.name, child_names):
                    add_or_create_key(self.exported_traded_energy_kwh,
                                      self.current_market.time_slot,
                                      trade.traded_energy)
                if area_sells_to_child(trade, self._area.name, child_names):
                    add_or_create_key(self.imported_traded_energy_kwh,
                                      self.current_market.time_slot,
                                      trade.traded_energy)
        if self.current_market.time_slot not in self.imported_traded_energy_kwh:
            self.imported_traded_energy_kwh[self.current_market.time_slot] = 0.
        if self.current_market.time_slot not in self.exported_traded_energy_kwh:
            self.exported_traded_energy_kwh[self.current_market.time_slot] = 0.

    def calculate_energy_deviances(self) -> None:
        """
        If area is a device - Get its forecated deviance
        Else accumulate energy deviances of connected children
        """
        current_market = (getattr(self._area, "current_market", None) or
                          getattr(self._area.parent, "current_market", None))
        if (current_market is None or
                ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS is False):
            return
        time_slot = current_market.time_slot
        if self._area.strategy is None:
            # Accumulating energy deviance of connected children
            self.total_energy_deviance_kWh[time_slot] = {
                child.uuid: child.stats.total_energy_deviance_kWh[time_slot]
                for child in self._area.children}
        elif isinstance(self._area.strategy, (PVStrategy, LoadHoursStrategy)):
            # Energy deviance of PV/LOAD
            self.total_energy_deviance_kWh[time_slot] = {
                self._area.uuid: self._area.strategy.state.get_forecast_measurement_deviation_kWh(
                    time_slot)
            }
        else:
            # Zero energy deviances of non-fluctuating devices
            self.total_energy_deviance_kWh[time_slot] = {self._area.uuid: 0.}
