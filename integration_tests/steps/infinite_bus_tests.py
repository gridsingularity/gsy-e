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
from behave import then, given
from math import isclose
from d3a import limit_float_precision
from d3a.models.config import ConstSettings
from d3a.d3a_core.sim_results.export_unmatched_loads import ExportUnmatchedLoads,\
    get_number_of_unmatched_loads


@given('the market type is {market_type}')
def set_market_type(context, market_type):
    ConstSettings.IAASettings.MARKET_TYPE = int(market_type)


@then('Infinite Bus buys energy that is not needed from the PV and sells to the load')
def check_buy_behaviour_ib(context):
    grid = context.simulation.area
    bus = list(filter(lambda x: x.name == "Infinite Bus", grid.children))[0]
    house_1 = list(filter(lambda x: x.name == "House 1", grid.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house_1.children))[0]
    load = list(filter(lambda x: x.name == "H1 General Load", house_1.children))[0]

    for market in grid.past_markets:
        for trade in market.trades:
            assert limit_float_precision(trade.offer.price / trade.offer.energy) <= \
                   bus.strategy.energy_rate[market.time_slot] + house_1.transfer_fee_const or \
                   "Infinite Bus" is not trade.seller

            if trade.buyer == load.name:
                assert trade.offer.energy == load.strategy.avg_power_W / 1000.
            elif trade.seller == bus.name:
                assert isclose(trade.offer.energy,
                               load.strategy.avg_power_W / 1000. -
                               pv.strategy.energy_production_forecast_kWh[market.time_slot])

    unmatched, unmatched_redis = \
        ExportUnmatchedLoads(context.simulation.area).get_current_market_results(
            all_past_markets=True)
    assert get_number_of_unmatched_loads(unmatched) == 0


@then('the infinite bus traded energy respecting its buy/sell rate')
def check_infinite_bus_traded_energy_rate(context):
    grid = context.simulation.area
    bus = list(filter(lambda x: x.name == "Infinite Bus", grid.children))[0]
    for market in grid.past_markets:
        for trade in market.trades:
            if trade.seller_origin == "Infinite Bus":
                assert isclose(trade.offer.price/trade.offer.energy,
                               bus.strategy.energy_rate[market.time_slot])
            if trade.buyer_origin == "Infinite Bus":
                assert isclose(trade.offer.price/trade.offer.energy,
                               bus.strategy.energy_buy_rate[market.time_slot])
