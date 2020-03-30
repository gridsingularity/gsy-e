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


@then('no trades are performed in all markets')
def no_trades_in_all_markets(context):
    grid = context.simulation.area
    assert all(len(market.trades) == 0 for market in grid.past_markets)
    house1 = [child for child in grid.children if child.name == "House 1"][0]
    assert all(len(market.trades) == 0 for market in house1.past_markets)
