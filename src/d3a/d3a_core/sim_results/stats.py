"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
from collections import OrderedDict
from copy import deepcopy
from itertools import chain
from d3a.d3a_core.util import round_floats_for_ui
from d3a.d3a_core.util import area_name_from_area_or_iaa_name
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.constants import DEVICE_PENALTY_RATE


def recursive_current_markets(area):
    if area.current_market is not None:
        yield area.current_market
        for child in area.children:
            yield from recursive_current_markets(child)


def _get_past_markets_from_area(area, past_market_types):
    if not hasattr(area, past_market_types) or getattr(area, past_market_types) is None:
        return []
    if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
        return getattr(area, past_market_types)
    else:
        if len(getattr(area, past_market_types)) < 1:
            return []
        return [getattr(area, past_market_types)[-1]]


def primary_trades(markets):
    """
    We want to avoid counting trades between different areas multiple times
    (as they are represented as a chain of trades with IAAs). To achieve
    this, we skip all trades where the buyer is an IAA.
    """
    for market in markets:
        for trade in market.trades:
            if trade.buyer[:4] != 'IAA ':
                yield trade
    # TODO find a less hacky way to exclude trades with IAAs as buyers


def primary_unit_prices(markets):
    for trade in primary_trades(markets):
        yield trade.offer.energy_rate


def total_avg_trade_price(markets):
    return (
        sum(trade.offer.price for trade in primary_trades(markets)) /
        sum(trade.offer.energy for trade in primary_trades(markets))
    )


class CumulativeBills:
    def __init__(self):
        self.cumulative_bills_results = {}

    def _calculate_device_penalties(self, area):
        if len(area.children) > 0:
            return

        if isinstance(area.strategy, LoadHoursStrategy):
            return sum(
                area.strategy.energy_requirement_Wh.get(market.time_slot, 0) / 1000.0
                for market in _get_past_markets_from_area(area.parent, "past_markets"))
        elif isinstance(area.strategy, PVStrategy):
            return sum(
                area.strategy.state.available_energy_kWh.get(market.time_slot, 0)
                for market in _get_past_markets_from_area(area.parent, "past_markets"))
        else:
            return None

    @property
    def cumulative_bills(self):
        return {
            uuid: {
                "name": results["name"],
                "spent_total": round_floats_for_ui(results['spent_total']),
                "earned": round_floats_for_ui(results['earned']),
                "penalties": round_floats_for_ui(results['penalties']),
                "total": round_floats_for_ui(results['total'])
            }
            for uuid, results in self.cumulative_bills_results.items()
        }

    def update_cumulative_bills(self, area):
        for child in area.children:
            self.update_cumulative_bills(child)

        if area.uuid not in self.cumulative_bills_results or \
                ConstSettings.GeneralSettings.KEEP_PAST_MARKETS is True:
            self.cumulative_bills_results[area.uuid] = {
                "name": area.name,
                "spent_total": 0.0,
                "earned": 0.0,
                "penalties": 0.0,
                "penalty_energy": 0.0,
                "total": 0.0,
            }

        if area.strategy is None:
            all_child_results = [self.cumulative_bills_results[c.uuid]
                                 for c in area.children]
            self.cumulative_bills_results[area.uuid] = {
                "name": area.name,
                "spent_total": sum(c["spent_total"] for c in all_child_results),
                "earned": sum(c["earned"] for c in all_child_results),
                "penalties": sum(c["penalties"] for c in all_child_results
                                 if c["penalties"] is not None),
                "penalty_energy": sum(c["penalty_energy"] for c in all_child_results
                                      if c["penalty_energy"] is not None),
                "total": sum(c["total"] for c in all_child_results),
            }
        else:
            trades = [m.trades
                      for m in _get_past_markets_from_area(area.parent, "past_markets")]
            trades = list(chain(*trades))

            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                spent_total = sum(trade.offer.price + trade.fee_price
                                  for trade in trades
                                  if trade.buyer == area.name) / 100.0
                earned = sum(trade.offer.price
                             for trade in trades
                             if trade.seller == area.name) / 100.0
            else:
                spent_total = sum(trade.offer.price
                                  for trade in trades
                                  if trade.buyer == area.name) / 100.0
                earned = sum(trade.offer.price - trade.fee_price
                             for trade in trades
                             if trade.seller == area.name) / 100.0
            penalty_energy = self._calculate_device_penalties(area)
            if penalty_energy is None:
                penalty_energy = 0.0
            penalty_cost = penalty_energy * DEVICE_PENALTY_RATE / 100.0
            total = spent_total - earned + penalty_cost
            self.cumulative_bills_results[area.uuid]["spent_total"] += spent_total
            self.cumulative_bills_results[area.uuid]["earned"] += earned
            self.cumulative_bills_results[area.uuid]["penalties"] += penalty_cost
            self.cumulative_bills_results[area.uuid]["penalty_energy"] += penalty_energy
            self.cumulative_bills_results[area.uuid]["total"] += total


class MarketEnergyBills:
    def __init__(self, is_spot_market=True):
        self.is_spot_market = is_spot_market
        self.bills_results = {}
        self.bills_redis_results = {}
        self.market_fees = {}
        self.external_trades = {}

    def _store_bought_trade(self, result_dict, trade):
        # Division by 100 to convert cents to Euros
        fee_price = trade.fee_price / 100. if trade.fee_price is not None else 0.
        result_dict['bought'] += trade.offer.energy
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            result_dict['spent'] += trade.offer.price / 100.
            result_dict['total_cost'] += trade.offer.price / 100. + fee_price
        else:
            result_dict['spent'] += trade.offer.price / 100. - fee_price
            result_dict['total_cost'] += trade.offer.price / 100.
        result_dict['total_energy'] += trade.offer.energy
        result_dict['market_fee'] += fee_price

    def _store_sold_trade(self, result_dict, trade):
        # Division by 100 to convert cents to Euros
        fee_price = trade.fee_price if trade.fee_price is not None else 0.
        result_dict['sold'] += trade.offer.energy
        result_dict['total_energy'] -= trade.offer.energy
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            trade_price = trade.offer.price
        else:
            trade_price = trade.offer.price - fee_price
        result_dict['earned'] += trade_price / 100.
        result_dict['total_cost'] -= trade_price / 100.

    def _store_outgoing_external_trade(self, trade, area):
        fee_price = trade.fee_price if trade.fee_price is not None else 0.
        self.external_trades[area.name]['sold'] += trade.offer.energy
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            self.external_trades[area.name]['earned'] += trade.offer.price / 100.
            self.external_trades[area.name]['total_cost'] -= trade.offer.price / 100.
        else:
            self.external_trades[area.name]['earned'] += \
                (trade.offer.price - fee_price) / 100.
            self.external_trades[area.name]['total_cost'] -= \
                (trade.offer.price - fee_price) / 100.
        self.external_trades[area.name]['total_energy'] -= trade.offer.energy
        self.external_trades[area.name]['market_fee'] += fee_price / 100.

    def _store_incoming_external_trade(self, trade, area):
        fee_price = trade.fee_price / 100. if trade.fee_price is not None else 0.
        self.external_trades[area.name]['bought'] += trade.offer.energy
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            self.external_trades[area.name]['spent'] += \
                trade.offer.price / 100.
            self.external_trades[area.name]['total_cost'] += \
                trade.offer.price / 100. + fee_price
        else:
            self.external_trades[area.name]['spent'] += \
                trade.offer.price / 100. - fee_price
            self.external_trades[area.name]['total_cost'] += \
                trade.offer.price / 100.
        self.external_trades[area.name]['total_energy'] += trade.offer.energy

    @classmethod
    def _default_area_dict(cls, area):
        return dict(bought=0.0, sold=0.0,
                    spent=0.0, earned=0.0,
                    total_energy=0.0, total_cost=0.0,
                    market_fee=0.0,
                    type=area.display_type)

    def _get_child_data(self, area):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            return {child.name: self._default_area_dict(child)
                    for child in area.children}
        else:
            if area.name not in self.bills_results:
                self.bills_results[area.name] =  \
                    {child.name: self._default_area_dict(child)
                        for child in area.children}
            return self.bills_results[area.name]

    def _get_child_instance(self, name, area):
        for child in area.children:
            if name == child.name:
                self.bills_results[area.name][name] = self._default_area_dict(child)
                return True

    def _energy_bills(self, area, past_market_types):
        """
        Return a bill for each of area's children with total energy bought
        and sold (in kWh) and total money earned and spent (in cents).
        Compute bills recursively for children of children etc.
        """
        if not area.children:
            return None

        if area.name not in self.external_trades or \
                ConstSettings.GeneralSettings.KEEP_PAST_MARKETS is True:
            self.external_trades[area.name] = dict(
                bought=0.0, sold=0.0, spent=0.0, earned=0.0,
                total_energy=0.0, total_cost=0.0, market_fee=0.0)

        result = self._get_child_data(area)
        for market in _get_past_markets_from_area(area, past_market_types):
            for trade in market.trades:
                buyer = area_name_from_area_or_iaa_name(trade.buyer)
                seller = area_name_from_area_or_iaa_name(trade.seller)
                if buyer in result:
                    self._store_bought_trade(result[buyer], trade)
                elif self._get_child_instance(buyer, area) and buyer in result:
                    self._store_bought_trade(result[buyer], trade)
                if seller in result:
                    self._store_sold_trade(result[seller], trade)
                elif self._get_child_instance(seller, area) and seller in result:
                    self._store_sold_trade(result[seller], trade)
                # Outgoing external trades
                if buyer == area_name_from_area_or_iaa_name(area.name) and seller in result:
                    self._store_outgoing_external_trade(trade, area)
                # Incoming external trades
                if seller == area_name_from_area_or_iaa_name(area.name) and buyer in result:
                    self._store_incoming_external_trade(trade, area)
        for child in area.children:
            child_result = self._energy_bills(child, past_market_types)
            if child_result is not None:
                result[child.name]['children'] = child_result

        return result

    def _accumulate_market_fees(self, area, past_market_types):
        if area.name not in self.market_fees:
            self.market_fees[area.name] = 0.0
        for market in _get_past_markets_from_area(area, past_market_types):
            # Converting cents to Euros
            self.market_fees[area.name] += market.market_fee / 100.0
        for child in area.children:
            self._accumulate_market_fees(child, past_market_types)

    def _update_market_fees(self, area, market_type):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            # If all the past markets remain in memory, reinitialize the market fees
            self.market_fees = {}
        self._accumulate_market_fees(area, market_type)

    def update(self, area):
        market_type = "past_markets" if self.is_spot_market else "past_balancing_markets"
        self._update_market_fees(area, market_type)
        bills = self._energy_bills(area, market_type)
        flattened = self._flatten_energy_bills(OrderedDict(sorted(bills.items())), {})
        self.bills_results = self._accumulate_by_children(area, flattened, {})
        self._bills_for_redis(area, deepcopy(self.bills_results))

    @classmethod
    def _flatten_energy_bills(cls, energy_bills, flat_results):
        for k, v in energy_bills.items():
            if k == "market_fee":
                flat_results["market_fee"] = v
                continue
            if "children" in v:
                cls._flatten_energy_bills(v["children"], flat_results)
            flat_results[k] = v
            flat_results[k].pop("children", None)
        return flat_results

    def _accumulate_by_children(self, area, flattened, results):
        if not area.children:
            # This is a device
            results[area.name] = flattened.get(area.name, self._default_area_dict(area))
        else:
            results[area.name] = {c.name: flattened[c.name] for c in area.children
                                  if c.name in flattened}

            results.update(**self._generate_external_and_total_bills(area, results, flattened))

            for c in area.children:
                results.update(
                    **self._accumulate_by_children(c, flattened, results)
                )
        return results

    def _write_acculumated_stats(self, area, results, all_child_results, key_name):
        results[area.name].update({key_name: {
            'bought': sum(v['bought'] for v in all_child_results),
            'sold': sum(v['sold'] for v in all_child_results),
            'spent': sum(v['spent'] for v in all_child_results),
            'earned': sum(v['earned'] for v in all_child_results),
            'total_energy': sum(v['total_energy'] for v in all_child_results),
            'total_cost': sum(v['total_cost']
                              for v in all_child_results),
            'market_fee': sum(v['market_fee']
                              for v in all_child_results)
        }})

    @staticmethod
    def _market_fee_section(market_fee):
        return {"Market Fees": {
                    "bought": 0,
                    "sold": 0,
                    "spent": 0,
                    "earned": market_fee,
                    "market_fee": 0,
                    "total_energy": 0,
                    "total_cost": -1 * market_fee
                    }}

    def _generate_external_and_total_bills(self, area, results, flattened):

        all_child_results = [v for v in results[area.name].values()]
        self._write_acculumated_stats(area, results, all_child_results, "Accumulated Trades")
        total_market_fee = results[area.name]["Accumulated Trades"]["market_fee"]
        if area.name in self.external_trades:
            # External trades are the trades of the parent area
            external = self.external_trades[area.name].copy()
            # Should switch spent/earned and bought/sold, to match the perspective of the UI
            spent = external.pop("spent")
            earned = external.pop("earned")
            bought = external.pop("bought")
            sold = external.pop("sold")
            total_external_fee = external.pop("market_fee")
            external.update(**{
                "spent": earned, "earned": spent, "bought": sold,
                "sold": bought, "market_fee": total_external_fee})
            external["total_energy"] = external["bought"] - external["sold"]
            external["total_cost"] = external["spent"] - external["earned"] + total_external_fee
            results[area.name].update({"External Trades": external})

            total_market_fee += total_external_fee
            results[area.name].update(self._market_fee_section(total_market_fee))
            totals_child_list = [results[area.name]["Accumulated Trades"],
                                 results[area.name]["External Trades"],
                                 results[area.name]["Market Fees"]]
        else:
            # If root area, Accumulated Trades == Totals
            results[area.name].update(self._market_fee_section(total_market_fee))
            totals_child_list = [results[area.name]["Accumulated Trades"],
                                 results[area.name]["Market Fees"]]

        self._write_acculumated_stats(area, results, totals_child_list, "Totals")
        return results

    def _bills_for_redis(self, area, bills_results):
        if area.name in bills_results:
            self.bills_redis_results[area.uuid] = \
                self._round_area_bill_result_redis(bills_results[area.name])
        for child in area.children:
            if child.children:
                self._bills_for_redis(child, bills_results)
            elif child.name in bills_results:
                self.bills_redis_results[child.uuid] = \
                    self._round_child_bill_results(bills_results[child.name])

    @classmethod
    def _round_child_bill_results(cls, results):
        results['bought'] = round_floats_for_ui(results['bought'])
        results['sold'] = round_floats_for_ui(results['sold'])
        results['spent'] = round_floats_for_ui(results['spent'])
        results['earned'] = round_floats_for_ui(results['earned'])
        results['total_energy'] = round_floats_for_ui(results['total_energy'])
        results['total_cost'] = round_floats_for_ui(results['total_cost'])
        if "market_fee" in results:
            results["market_fee"] = round_floats_for_ui(results['market_fee'])
        return results

    @classmethod
    def _round_area_bill_result_redis(cls, results):
        for k in results.keys():
            results[k] = cls._round_child_bill_results(results[k])
        return results
