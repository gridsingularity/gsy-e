"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from gsy_e import limit_float_precision
from gsy_framework.utils import get_area_name_uuid_mapping
from gsy_e.models.config import ConstSettings


@given('the market type is {market_type}')
def set_market_type(context, market_type):
    ConstSettings.MASettings.MARKET_TYPE = int(market_type)


@then('Infinite Bus buys energy that is not needed from the PV and sells to the load')
def check_buy_behaviour_ib(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    name_uuid_map = get_area_name_uuid_mapping(context.area_tree_summary_data)
    grid = context.simulation.area
    bus = list(filter(lambda x: x.name == "Infinite Bus", grid.children))[0]
    for time_slot, core_stats in context.raw_sim_data.items():
        for trade in core_stats[name_uuid_map['Grid']]['trades']:
            if trade['seller'] == "Infinite Bus":
                assert limit_float_precision(trade['energy_rate']) >= \
                       core_stats[name_uuid_map['Infinite Bus']]['energy_rate']
            else:
                assert limit_float_precision(trade['energy_rate']) <= \
                       core_stats[name_uuid_map['Infinite Bus']]['energy_rate']

            if trade['buyer'] == "Infinite Bus":
                # TODO: energy_buy_rate is not part of the raw simulation data, therefore
                # it is obligatory to retrieve it from the strategy. This needs to change once
                # we add the energy_buy_rate to the infinite bus result data.
                assert limit_float_precision(trade['energy_rate']) <= \
                       list(bus.strategy.energy_buy_rate.values())[0]

            if trade['buyer'] == "H1 General Load":
                assert trade['energy'] == \
                       core_stats[name_uuid_map['H1 General Load']]['load_profile_kWh']
            elif trade['seller'] == 'Infinite Bus':
                assert isclose(trade['energy'],
                               (core_stats[name_uuid_map['H1 General Load']]['load_profile_kWh'] -
                                core_stats[name_uuid_map['H1 PV']]['pv_production_kWh']))


@then('the infinite bus traded energy respecting its buy/sell rate')
def check_infinite_bus_traded_energy_rate(context):
    grid = context.simulation.area
    bus = list(filter(lambda x: x.name == "Infinite Bus", grid.children))[0]
    for market in grid.past_markets:
        for trade in market.trades:
            if trade.seller_origin == "Infinite Bus":
                assert isclose(trade.offer_bid.price/trade.offer_bid.energy,
                               bus.strategy.energy_rate[market.time_slot])
            if trade.buyer_origin == "Infinite Bus":
                assert isclose(trade.offer_bid.price/trade.offer_bid.energy,
                               bus.strategy.energy_buy_rate[market.time_slot])
