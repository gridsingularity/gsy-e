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


class MarketEnergyBills:
    def __init__(self, is_spot_market=True):
        self.is_spot_market = is_spot_market
        self.bills_results = {}
        self.bills_redis_results = {}
        self.market_fees = {}

    @classmethod
    def _store_bought_trade(cls, result_dict, trade):
        # Division by 100 to convert cents to Euros
        fee_price = trade.fee_price / 100. if trade.fee_price is not None else 0.
        result_dict['bought'] += trade.offer.energy
        result_dict['spent'] += trade.offer.price / 100. - fee_price
        result_dict['total_energy'] += trade.offer.energy
        result_dict['total_cost'] += trade.offer.price / 100.
        result_dict['market_fee'] += fee_price

    @classmethod
    def _store_sold_trade(cls, result_dict, trade):
        # Division by 100 to convert cents to Euros
        fee_price = trade.fee_price if trade.fee_price is not None else 0.
        result_dict['sold'] += trade.offer.energy
        result_dict['earned'] += (trade.offer.price - fee_price) / 100.
        result_dict['total_energy'] -= trade.offer.energy
        result_dict['total_cost'] -= (trade.offer.price - fee_price) / 100.

    @classmethod
    def _get_past_markets_from_area(cls, area, past_market_types):
        if not hasattr(area, past_market_types) or getattr(area, past_market_types) is None:
            return []
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            return getattr(area, past_market_types)
        else:
            if len(getattr(area, past_market_types)) < 1:
                return []
            return [getattr(area, past_market_types)[-1]]

    def _default_area_dict(self, area):
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

    def _store_area_penalties(self, results_dict, area):
        if len(area.children) > 0:
            return
        if isinstance(area.strategy, LoadHoursStrategy):
            penalty_energy = sum(
                area.strategy.energy_requirement_Wh.get(market.time_slot, 0) / 1000.0
                for market in self._get_past_markets_from_area(area.parent, "past_markets"))
        elif isinstance(area.strategy, PVStrategy):
            penalty_energy = sum(
                area.strategy.state.available_energy_kWh.get(market.time_slot, 0)
                for market in self._get_past_markets_from_area(area.parent, "past_markets"))
        else:
            results_dict["totals_with_penalties"] = results_dict["total_cost"]
            return
        if "penalty_energy" not in results_dict:
            results_dict["penalty_energy"] = 0.0
            results_dict["penalty_cost"] = 0.0

        results_dict["penalty_energy"] += penalty_energy
        # Penalty cost unit should be Euro
        results_dict["penalty_cost"] += penalty_energy * DEVICE_PENALTY_RATE / 100.0
        results_dict["totals_with_penalties"] = \
            results_dict["total_cost"] + results_dict["penalty_cost"]

    def _energy_bills(self, area, past_market_types):
        """
        Return a bill for each of area's children with total energy bought
        and sold (in kWh) and total money earned and spent (in cents).
        Compute bills recursively for children of children etc.
        """
        if not area.children:
            return None
        result = self._get_child_data(area)
        for market in self._get_past_markets_from_area(area, past_market_types):
            for trade in market.trades:
                buyer = area_name_from_area_or_iaa_name(trade.buyer)
                seller = area_name_from_area_or_iaa_name(trade.seller)
                if buyer in result:
                    self._store_bought_trade(result[buyer], trade)
                if seller in result:
                    self._store_sold_trade(result[seller], trade)
        for child in area.children:
            self._store_area_penalties(result[child.name], child)
            child_result = self._energy_bills(child, past_market_types)
            if child_result is not None:
                result[child.name]['children'] = child_result

        return result

    def _accumulate_market_fees(self, area, past_market_types):
        if area.name not in self.market_fees:
            self.market_fees[area.name] = 0.0
        for market in self._get_past_markets_from_area(area, past_market_types):
            # Converting cents to Euros
            self.market_fees[market.name] += market.market_fee / 100.0
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
        self._aggregate_totals_with_penalties(area, self.bills_results)
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

    def _aggregate_totals_with_penalties(self, area, results):
        if not area.children:
            return
        totals_with_penalties = 0
        for child in area.children:
            self._aggregate_totals_with_penalties(child, results)
            if "totals_with_penalties" in results[child.name]:
                if isinstance(results[child.name]["totals_with_penalties"], dict):
                    totals_with_penalties += results[child.name]["totals_with_penalties"]["costs"]
                else:
                    totals_with_penalties += results[child.name]["totals_with_penalties"]
        results[area.name]["totals_with_penalties"] = {"costs": totals_with_penalties}

    def _generate_external_and_total_bills(self, area, results, flattened):
        all_child_results = [v for v in results[area.name].values()]
        results[area.name].update({"Accumulated Trades": {
            'bought': sum(v['bought'] for v in all_child_results),
            'sold': sum(v['sold'] for v in all_child_results),
            'spent': sum(v['spent'] for v in all_child_results),
            'earned': sum(v['earned'] for v in all_child_results) + self.market_fees[area.name],
            'penalty_cost': sum(v['penalty_cost']
                                for v in all_child_results if 'penalty_cost' in v.keys()),
            'penalty_energy': sum(v['penalty_energy']
                                  for v in all_child_results if 'penalty_energy' in v.keys()),
            'total_energy': sum(v['total_energy'] for v in all_child_results),
            'total_cost': sum(v['total_cost']
                              for v in all_child_results) - self.market_fees[area.name],
            'market_fee': sum(v['market_fee']
                              for v in all_child_results)
        }})

        if area.name in flattened:
            # External trades are the trades of the parent area
            external = flattened[area.name].copy()
            # Should not include market fee to the external trades
            market_fee = external.pop("market_fee", 0.)
            # Should switch spent/earned and bought/sold, to match the perspective of the UI
            spent = external.pop("spent") + market_fee
            earned = external.pop("earned")
            bought = external.pop("bought")
            sold = external.pop("sold")
            external.update(**{
                "spent": earned, "earned": spent, "bought": sold,
                "sold": bought, "market_fee": 0})
            external["total_energy"] = external["bought"] - external["sold"]
            external["total_cost"] = external["spent"] - external["earned"]
            results[area.name].update({"External Trades": external})
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
        if "penalty_energy" in results:
            results["penalty_energy"] = round_floats_for_ui(results['penalty_energy'])
        if "penalty_cost" in results:
            results["penalty_cost"] = round_floats_for_ui(results['penalty_cost'])
        if "totals_with_penalties" in results:
            results["totals_with_penalties"] = \
                round_floats_for_ui(results["totals_with_penalties"])
        return results

    @classmethod
    def _round_area_bill_result_redis(cls, results):
        for k in results.keys():
            if k == "totals_with_penalties" and isinstance(results[k], dict):
                results[k]["costs"] = round_floats_for_ui(results[k]["costs"])
            else:
                results[k] = cls._round_child_bill_results(results[k])
        return results
