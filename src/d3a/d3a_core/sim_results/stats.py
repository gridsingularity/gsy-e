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
from d3a.d3a_core.util import area_name_from_area_or_iaa_name
from d3a.models.const import ConstSettings


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
    def __init__(self):
        self.results = {}

    @classmethod
    def _store_bought_trade(cls, result_dict, trade_offer):
        result_dict['bought'] += trade_offer.energy
        result_dict['spent'] += trade_offer.price / 100.
        result_dict['total_energy'] += trade_offer.energy
        result_dict['total_cost'] += trade_offer.price / 100.

    @classmethod
    def _store_sold_trade(cls, result_dict, trade_offer):
        result_dict['sold'] += trade_offer.energy
        result_dict['earned'] += trade_offer.price / 100.
        result_dict['total_energy'] -= trade_offer.energy
        result_dict['total_cost'] -= trade_offer.price / 100.

    @classmethod
    def _get_past_markets_from_area(cls, area, past_market_types):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            return getattr(area, past_market_types)
        else:
            return [getattr(area, past_market_types)[-1]]

    def _get_child_data(self, area):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            return {child.name: dict(bought=0.0, sold=0.0,
                                     spent=0.0, earned=0.0,
                                     total_energy=0, total_cost=0,
                                     type=child.display_type)
                    for child in area.children}
        else:
            if area.name not in self.results:
                self.results[area.name] =  \
                    {child.name: dict(bought=0.0, sold=0.0,
                                      spent=0.0, earned=0.0,
                                      total_energy=0, total_cost=0,
                                      type=child.display_type)
                        for child in area.children}
            return self.results[area.name]

    def energy_bills(self, area, past_market_types):
        """
        Return a bill for each of area's children with total energy bought
        and sold (in kWh) and total money earned and spent (in cents).
        Compute bills recursively for children of children etc.
        """
        if not area.children:
            return None
        result = self._get_child_data(area)
        result["market_fee"] = 0
        for market in self._get_past_markets_from_area(area, past_market_types):
            result["market_fee"] += market.market_fee
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
                result[child.name]['market_fee'] = child_result.pop("market_fee")
                result[child.name]['children'] = child_result

        return result

    def update(self, area, past_market_types):
        self.results = self.energy_bills(area, past_market_types)
        return self.results
