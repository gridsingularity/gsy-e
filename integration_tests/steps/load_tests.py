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

from gsy_framework.read_user_profile import read_arbitrary_profile, InputProfileTypes, \
    _str_to_datetime
from gsy_framework.utils import convert_W_to_Wh, find_object_of_same_weekday_and_time
from gsy_e.setup.strategy_tests import user_profile_load_csv  # NOQA
from gsy_e.setup.strategy_tests import user_profile_load_csv_multiday  # NOQA
from gsy_e.constants import FLOATING_POINT_TOLERANCE, DATE_TIME_FORMAT


@then('the DefinedLoadStrategy follows the {single_or_multi} day Load profile provided as csv')
def check_load_profile_csv(context, single_or_multi):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: x.name == "H1 DefinedLoad", house1.children))
    if single_or_multi == "single":
        path = user_profile_load_csv.profile_path
    else:
        path = user_profile_load_csv_multiday.profile_path
    input_profile = read_arbitrary_profile(InputProfileTypes.POWER, path)
    for timepoint, energy in load.strategy.state._desired_energy_Wh.items():
        assert energy == find_object_of_same_weekday_and_time(input_profile, timepoint) * 1000


@then('load only accepted offers lower than final_buying_rate')
def check_traded_energy_rate(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: "H1 DefinedLoad" in x.name, house.children))

    for market in house.past_markets:
        for trade in market.trades:
            if trade.buyer == load.name:
                assert trade.offer_bid.energy_rate < \
                       load.strategy.bid_update.final_rate[market.time_slot]


@then('the DefinedLoadStrategy follows the Load profile provided as dict')
def check_user_pv_dict_profile(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: x.name == "H1 DefinedLoad", house.children))
    from gsy_e.setup.strategy_tests.user_profile_load_dict import user_profile

    for market in house.past_markets:
        slot = market.time_slot
        if slot.hour in user_profile.keys():
            assert load.strategy.state._desired_energy_Wh[slot] == \
                   convert_W_to_Wh(user_profile[slot.hour], house.config.slot_length)
        else:
            if int(slot.hour) > int(list(user_profile.keys())[-1]):
                assert load.strategy.state._desired_energy_Wh[slot] == \
                       convert_W_to_Wh(user_profile[list(user_profile.keys())[-1]],
                                       house.config.slot_length)
            else:
                assert load.strategy.state._desired_energy_Wh[slot] == 0


@then('LoadHoursStrategy does not buy energy with rates that are higher than the provided profile')
def check_user_rate_profile_dict(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load1 = next(filter(lambda x: x.name == "H1 General Load 1", house.children))
    load2 = next(filter(lambda x: x.name == "H1 General Load 2", house.children))
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    for time_slot, core_stats in context.raw_sim_data.items():
        slot = _str_to_datetime(time_slot, DATE_TIME_FORMAT)
        load1_final_rate = load1.strategy.bid_update.final_rate_profile_buffer[slot]
        load2_final_rate = load2.strategy.bid_update.final_rate_profile_buffer[slot]
        load1_trades = \
            list(filter(lambda x:
                        x["energy_rate"] > load1_final_rate,
                        core_stats[context.name_uuid_map["H1 General Load 1"]]["trades"]))
        load2_trades = \
            list(filter(lambda x: x["energy_rate"] > load2_final_rate,
                        core_stats[context.name_uuid_map["H1 General Load 2"]]["trades"]))

        assert len(load1_trades) == 0 and len(load2_trades) == 0


@then('LoadHoursStrategy buys energy with rates equal to the initial buying rate profile')
def check_min_user_rate_profile_dict(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load1 = next(filter(lambda x: x.name == "H1 General Load 1", house.children))
    load2 = next(filter(lambda x: x.name == "H1 General Load 2", house.children))

    for market in house.past_markets:
        assert len(market.trades) > 0
        for trade in market.trades:
            trade_rate = trade.offer_bid.energy_rate
            if trade.buyer == load1.name:
                min_rate = load1.strategy.bid_update.initial_rate[market.time_slot]
                assert trade_rate - min_rate < FLOATING_POINT_TOLERANCE
            elif trade.buyer == load2.name:
                min_rate = load2.strategy.bid_update.initial_rate[market.time_slot]
                assert trade_rate - min_rate < FLOATING_POINT_TOLERANCE
            else:
                assert False, "All trades should be bought by load1 or load2, no other consumer."


@then('LoadHoursStrategy buys energy at the final_buying_rate')
def check_bid_update_frequency(context):
    for time_slot, core_stats in context.raw_sim_data.items():
        for trade in core_stats[context.name_uuid_map['House 1']]['trades']:
            if trade['buyer'] == 'H1 General Load':
                assert isclose(trade['energy_rate'], 35)
            else:
                assert False, "All trades should be bought by load1, no other consumer."
