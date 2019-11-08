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
        yield trade.offer.price / trade.offer.energy


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
    def _store_bought_trade(cls, result_dict, trade_offer):
        # Division by 100 to convert cents to Euros
        result_dict['bought'] += trade_offer.energy
        result_dict['spent'] += trade_offer.price / 100.
        result_dict['total_energy'] += trade_offer.energy
        result_dict['total_cost'] += trade_offer.price / 100.

    @classmethod
    def _store_sold_trade(cls, result_dict, trade_offer):
        # Division by 100 to convert cents to Euros
        result_dict['sold'] += trade_offer.energy
        result_dict['earned'] += trade_offer.price / 100.
        result_dict['total_energy'] -= trade_offer.energy
        result_dict['total_cost'] -= trade_offer.price / 100.

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

    def _get_child_data(self, area):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            return {child.name: dict(bought=0.0, sold=0.0,
                                     spent=0.0, earned=0.0,
                                     total_energy=0.0, total_cost=0.0,
                                     type=child.display_type)
                    for child in area.children}
        else:
            if area.name not in self.bills_results:
                self.bills_results[area.name] =  \
                    {child.name: dict(bought=0.0, sold=0.0,
                                      spent=0.0, earned=0.0,
                                      total_energy=0.0, total_cost=0.0,
                                      type=child.display_type)
                        for child in area.children}
            return self.bills_results[area.name]

    def energy_bills(self, area, past_market_types):
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
                    self._store_bought_trade(result[buyer], trade.offer)
                if seller in result:
                    self._store_sold_trade(result[seller], trade.offer)
        for child in area.children:
            child_result = self.energy_bills(child, past_market_types)
            if child_result is not None:
                result[child.name]['children'] = child_result
                result[child.name]['market_fee'] = self.market_fees[child.name]

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
        bills = self.energy_bills(area, market_type)
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
            results[area.name] = flattened[area.name]
        else:
            results[area.name] = {c.name: flattened[c.name] for c in area.children}

            results.update(**self._generate_external_and_total_bills(area, results, flattened))

            for c in area.children:
                results.update(
                    **self._accumulate_by_children(c, flattened, results)
                )
        return results

    def _generate_external_and_total_bills(self, area, results, flattened):
        all_child_results = [v for v in results[area.name].values()]
        results[area.name].update({"Accumulated Trades": {
            'bought': sum(v['bought'] for v in all_child_results),
            'sold': sum(v['sold'] for v in all_child_results),
            'spent': sum(v['spent'] for v in all_child_results),
            'earned': sum(v['earned'] for v in all_child_results),
            'total_energy': sum(v['total_energy'] for v in all_child_results),
            'total_cost': sum(v['total_cost'] for v in all_child_results),
            'market_fee': self.market_fees[area.name]
        }})

        if area.name in flattened:
            external = {k: v for k, v in flattened[area.name].items() if k != 'market_fee'}
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
        return results

    @classmethod
    def _round_area_bill_result_redis(cls, results):
        for k in results.keys():
            results[k] = cls._round_child_bill_results(results[k])
        return results
