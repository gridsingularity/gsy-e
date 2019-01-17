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


def get_trade_rates_house1(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    return [
        (market, trade.offer.price / trade.offer.energy)
        for market in house1.past_markets
        for trade in market.trades
    ]


@then('average trade rate is the MMR until {time}')
def average_trade_rate_mmr_time(context, time):
    trade_rates = get_trade_rates_house1(context)
    assert all([isclose(
        context.simulation.simulation_config.market_maker_rate[tt[0].time_slot_str], tt[1])
                for tt in trade_rates
                if tt[0].time_slot.hour < int(time)])


@then('average trade rate after {time} is {trade_rate}')
def average_trade_rate_rate_time(context, time, trade_rate):
    trade_rates = get_trade_rates_house1(context)
    assert all([isclose(float(trade_rate), tt[1])
                for tt in trade_rates
                if tt[0].time_slot.hour > int(time)])
