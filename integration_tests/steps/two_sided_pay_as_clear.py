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
from math import isclose
from behave import then


@then('all trades are equal to market_clearing_rate')
def test_traded_energy_rate(context):
    grid = context.simulation.area
    for child in grid.children:
        for a, b in child.dispatcher.interarea_agents.items():
            for c in b:
                for d in c.engines:
                    for trade in d.markets.source.trades:
                        if len(d.clearing_rate) > 0:
                            assert any([isclose((trade.offer.price/trade.offer.energy), rate)
                                        for rate in d.clearing_rate])
