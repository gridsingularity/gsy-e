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


@then('Infinite Bus buys energy that is not needed from the PV')
def check_buy_behaviour_ib(context):
    grid = context.simulation.area
    bus = list(filter(lambda x: x.name == "Infinite Bus", grid.children))[0]
    house_1 = list(filter(lambda x: x.name == "House 1", grid.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house_1.children))[0]
    load = list(filter(lambda x: x.name == "H1 General Load", house_1.children))[0]

    for market in grid.past_markets:
        for trade in market.trades:
            assert trade.offer.price / trade.offer.energy <= \
                bus.strategy.energy_rate[market.time_slot]
            assert trade.buyer == bus.name
            assert trade.offer.energy == \
                pv.strategy.energy_production_forecast_kWh[market.time_slot] \
                - load.strategy.avg_power_W / 1000.


@then('Infinite Bus buys energy from the PV and sells to the load')
def check_buy_behaviour_ib_two_sided(context):
    grid = context.simulation.area
    bus = list(filter(lambda x: x.name == "Infinite Bus", grid.children))[0]
    house_1 = list(filter(lambda x: x.name == "House 1", grid.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house_1.children))[0]
    load = list(filter(lambda x: x.name == "H1 General Load", house_1.children))[0]

    for market in grid.past_markets:
        for trade in market.trades:
            if trade.buyer == bus.name:
                assert trade.offer.energy == \
                       pv.strategy.energy_production_forecast_kWh[market.time_slot]
            elif trade.seller == bus.name:
                assert trade.offer.energy == load.strategy.avg_power_W / 1000.
