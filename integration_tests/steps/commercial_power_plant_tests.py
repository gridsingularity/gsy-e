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
from behave import then
from math import isclose
from d3a_interface.constants_limits import GlobalConfig


@then('all trades are using the market maker rate from the strategy ({energy_rate})')
def trades_follow_strategy_mmr(context, energy_rate):
    grid = context.simulation.area
    load = [child for child in grid.children if child.name == "Load"][0]
    for market in load.past_markets:
        for trade in market.trades:
            assert isclose(trade.offer.price / trade.offer.energy, float(energy_rate))


@then('no trades are performed')
def no_trades_performed(context):
    grid = context.simulation.area
    load = [child for child in grid.children if child.name == "Load"][0]
    assert all(len(market.trades) == 0 for market in load.past_markets)


@then('the simulation market maker rate is the same as the strategy ({energy_rate})')
def mmr_follows_market_maker_strategy_rate(context, energy_rate):
    assert all(isclose(v, float(energy_rate)) for v in GlobalConfig.market_maker_rate.values())
