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
from pendulum import duration
from math import isclose

from d3a.setup.strategy_tests import user_profile_load_csv  # NOQA
from d3a.setup.strategy_tests import user_profile_load_csv_multiday  # NOQA
from d3a.d3a_core.sim_results.export_unmatched_loads import export_unmatched_loads


@then('the DefinedLoadStrategy follows the {single_or_multi} day Load profile provided as csv')
def check_load_profile_csv(context, single_or_multi):
    from d3a.models.read_user_profile import _readCSV
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: x.name == "H1 DefinedLoad", house1.children))
    if single_or_multi == "single":
        path = user_profile_load_csv.profile_path
    else:
        path = user_profile_load_csv_multiday.profile_path
    input_profile = _readCSV(path)
    desired_energy_Wh = load.strategy.state.desired_energy_Wh
    for timepoint, energy in desired_energy_Wh.items():
        if timepoint in input_profile.keys():
            assert energy == input_profile[timepoint] / \
                   (duration(hours=1) / load.config.slot_length)
        else:
            assert False


@then('load only accepted offers lower than final_buying_rate')
def check_traded_energy_rate(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: "H1 DefinedLoad" in x.name, house.children))

    for market in house.past_markets:
        for trade in market.trades:
            if trade.buyer == load.name:
                assert (trade.offer.price / trade.offer.energy) < \
                       load.strategy.final_buying_rate[market.time_slot]


@then('the DefinedLoadStrategy follows the Load profile provided as dict')
def check_user_pv_dict_profile(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: x.name == "H1 DefinedLoad", house.children))
    from d3a.setup.strategy_tests.user_profile_load_dict import user_profile

    for market in house.past_markets:
        slot = market.time_slot
        if slot.hour in user_profile.keys():
            assert load.strategy.state.desired_energy_Wh[slot] == user_profile[slot.hour] / \
                   (duration(hours=1) / house.config.slot_length)
        else:
            if int(slot.hour) > int(list(user_profile.keys())[-1]):
                assert load.strategy.state.desired_energy_Wh[slot] == \
                       user_profile[list(user_profile.keys())[-1]] / \
                       (duration(hours=1) / house.config.slot_length)
            else:
                assert load.strategy.state.desired_energy_Wh[slot] == 0


@then('LoadHoursStrategy does not buy energy with rates that are higher than the provided profile')
def check_user_rate_profile_dict(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))

    unmatched = export_unmatched_loads(context.simulation.area)
    number_of_loads = 2
    # There are two loads with the same final_buying_rate profile that should report unmatched
    # energy demand for the first 6 hours of the day:
    assert unmatched["unmatched_load_count"] == int(number_of_loads * 6. * 60 /
                                                    house.config.slot_length.minutes)


@then('LoadHoursStrategy buys energy with rates equal to the min rate profile')
def check_min_user_rate_profile_dict(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load1 = next(filter(lambda x: x.name == "H1 General Load 1", house.children))
    load2 = next(filter(lambda x: x.name == "H1 General Load 2", house.children))

    for market in house.past_markets:
        assert len(market.trades) > 0
        for trade in market.trades:
            if trade.buyer == load1.name:
                assert int(trade.offer.price / trade.offer.energy) == \
                       int(load1.strategy.initial_buying_rate[market.time_slot])
            elif trade.buyer == load2.name:
                assert int(trade.offer.price / trade.offer.energy) == \
                       int(load2.strategy.initial_buying_rate[market.time_slot])
            else:
                assert False, "All trades should be bought by load1 or load2, no other consumer."


@then('LoadHoursStrategy buys energy at the final_buying_rate')
def check_bid_update_frequency(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load1 = next(filter(lambda x: x.name == "H1 General Load", house.children))

    for market in house.past_markets:
        assert len(market.trades) > 0
        for trade in market.trades:
            if trade.buyer == load1.name:
                assert isclose((trade.offer.price / trade.offer.energy),
                               (load1.strategy.final_buying_rate[market.time_slot]))
            else:
                assert False, "All trades should be bought by load1, no other consumer."
