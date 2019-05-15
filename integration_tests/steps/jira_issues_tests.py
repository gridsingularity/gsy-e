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
from d3a.d3a_core.sim_results.export_unmatched_loads import ExportUnmatchedLoads, \
    get_number_of_unmatched_loads
from d3a.d3a_core.export import EXPORT_DEVICE_VARIABLES


def get_areas_from_2_house_grid(context):
    def filter_iaa(x):
        return x.name == "House 1" or \
               x.name == "House 2" or \
               x.name == "Grid"

    return list(filter(filter_iaa,
                       context.simulation.area.children))


@then('average trade rate is constant for every market slot for all markets')
def average_trade_rate_constant(context):
    areas = get_areas_from_2_house_grid(context)

    for area in areas:
        trade_rates = [
            trade.offer.price / trade.offer.energy
            for market in area.past_markets
            for trade in market.trades
        ]

        assert all(isclose(t, trade_rates[0], abs_tol=0.01) for t in trade_rates[1:])


@then('there are no trades with the same seller and buyer name')
def same_seller_buyer_name_check(context):
    areas = get_areas_from_2_house_grid(context)

    trades = [
        trade
        for area in areas
        for market in area.past_markets
        for trade in market.trades
    ]

    assert all(trade.buyer != trade.seller for trade in trades)


@then('storage buys energy from the commercial producer')
def storage_commercial_trades(context):
    house1 = [child for child in context.simulation.area.children
              if child.name == "House 1"][0]

    storage_trades = [
        trade
        for market in house1.past_markets
        for trade in market.trades
        if trade.buyer == "H1 Storage1"
    ]

    commercial_trades = [
        trade
        for market in context.simulation.area.past_markets
        for trade in market.trades
        if trade.seller == "Commercial Energy Producer"
    ]

    assert len(storage_trades) > 0
    assert len(commercial_trades) > 0
    assert len(storage_trades) == len(commercial_trades)


@then('storage final SOC is 100%')
def storage_final_soc(context):
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    storage = [child for child in house1.children if child.name == "H1 Storage1"][0]
    assert isclose(list(storage.strategy.state.charge_history.values())[-1], 100.0)


@then('storage buys energy respecting the break even buy threshold')
def step_impl(context):
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    storage = [child for child in house1.children if child.name == "H1 Storage1"][0]

    storage_trades = [
        trade
        for market in storage.past_markets
        for trade in market.trades
        if trade.buyer == "H1 Storage1"
    ]

    assert all([trade.offer.price / trade.offer.energy < 16.99 for trade in storage_trades])


@then('on every market slot there should be matching trades on grid and house markets')
def check_matching_trades(context):
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    grid = context.simulation.area

    for market in grid.past_markets:
        timeslot = market.time_slot
        assert house1.get_past_market(timeslot)
        grid_trades = grid.get_past_market(timeslot).trades
        house_trades = house1.get_past_market(timeslot).trades
        assert len(grid_trades) == len(house_trades)
        assert all(
            any(t.offer.energy == th.offer.energy and t.buyer == th.seller for th in house_trades)
            for t in grid_trades)


@then('there should be no unmatched loads')
def no_unmatched_loads(context):
    unmatched, unmatched_redis = ExportUnmatchedLoads(context.simulation.area)()
    assert get_number_of_unmatched_loads(unmatched) == 0


@then('pv produces the same energy on each corresponding time slot regardless of the day')
def pv_produces_same_amount_of_energy_day(context):
    house2 = [child for child in context.simulation.area.children if child.name == "House 2"][0]

    for base_market in house2.past_markets:
        timeslot = base_market.time_slot
        same_time_markets = [market for market in house2.past_markets
                             if market.time_slot.hour == timeslot.hour and
                             market.time_slot.minute == timeslot.minute]
        same_time_markets_energy = [sum(trade.offer.energy
                                        for trade in market.trades
                                        if trade.seller == "H2 PV")
                                    for market in same_time_markets]
        print(same_time_markets_energy)
        assert all(isclose(same_time_markets_energy[0], energy)
                   for energy in same_time_markets_energy)


def _assert_sum_of_energy_is_same_for_same_time(area, load_name):
    for base_market in area.past_markets:
        timeslot = base_market.time_slot
        same_time_markets = [market for market in area.past_markets
                             if market.time_slot.hour == timeslot.hour and
                             market.time_slot.minute == timeslot.minute]
        same_time_markets_energy = [sum(trade.offer.energy
                                        for trade in market.trades
                                        if trade.buyer == load_name)
                                    for market in same_time_markets]
        assert all(isclose(same_time_markets_energy[0], energy)
                   for energy in same_time_markets_energy)


@then('all loads consume the same energy on each corresponding time slot regardless of the day')
def loads_consume_same_amount_of_energy_day(context):
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    house2 = [child for child in context.simulation.area.children if child.name == "House 2"][0]

    _assert_sum_of_energy_is_same_for_same_time(house1, "H1 General Load")
    _assert_sum_of_energy_is_same_for_same_time(house2, "H2 General Load")


def _assert_hours_of_day(area, device):
    for market in area.past_markets:
        total_energy = sum(trade.offer.energy
                           for trade in market.trades if trade.buyer == device.name)
        if market.time_slot.hour not in device.strategy.hrs_of_day:
            assert isclose(total_energy, 0.0)
        else:
            assert isclose(total_energy, device.strategy.energy_per_slot_Wh / 1000.0)


@then('all loads adhere to the hours of day configuration')
def loads_adhere_to_hours_of_day_multiday(context):
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    h1_load = [child for child in house1.children if child.name == "H1 General Load"][0]
    house2 = [child for child in context.simulation.area.children if child.name == "House 2"][0]
    h2_load = [child for child in house2.children if child.name == "H2 General Load"][0]

    _assert_hours_of_day(house1, h1_load)
    _assert_hours_of_day(house2, h2_load)


@then('there should be a reported SOC of 0.1 on the first market')
def reported_soc_zero_on_first_slot(context):
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    electro = [child for child in house1.children if child.name == "H1 Electrolyser"][0]
    assert isclose(list(electro.strategy.state.charge_history.values())[0], 10.0)


@then('there should be trades on all markets using the max load rate')
def trades_on_all_markets_max_load_rate(context):
    grid = context.simulation.area
    house1 = [child for child in grid.children if child.name == "House 1"][0]
    load1 = [child for child in house1.children if child.name == "H1 General Load"][0]
    max_rate = load1.strategy.final_buying_rate

    for market in grid.past_markets:
        assert len(market.trades) == 1
        assert all(t.seller == "Commercial Energy Producer" for t in market.trades)
        assert all(t.buyer == "IAA House 1" for t in market.trades)
        assert all(isclose(t.offer.price / t.offer.energy, max_rate[market.time_slot])
                   for t in market.trades)

    for market in house1.past_markets:
        assert len(market.trades) == 1
        assert all(t.seller == "IAA House 1" for t in market.trades)
        assert all(t.buyer == "H1 General Load" for t in market.trades)
        assert all(isclose(t.offer.price / t.offer.energy, max_rate[market.time_slot])
                   for t in market.trades)


@then('the Load of House 1 should only buy energy from IAA between 5:00 and 8:00')
def house1_load_only_from_iaa(context):
    from d3a.models.const import ConstSettings
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    load1 = [child for child in house1.children if child.name == "H1 General Load"][0]

    for market in load1.past_markets:
        if not 5 <= market.time_slot.hour < 8:
            continue

        assert len(market.trades) == 1
        assert market.trades[0].offer.seller == \
            ConstSettings.GeneralSettings.ALT_PRICING_MARKET_MAKER_NAME


@then('the Commercial Producer should never sell energy')
def commercial_never_trades(context):
    commercial = [child for child in context.simulation.area.children
                  if child.name == "Commercial Energy Producer"][0]
    assert all(len(m.trades) == 0 for m in commercial.past_markets)


@then('the device statistics are correct')
def device_statistics(context):
    output_dict = context.simulation.endpoint_buffer.device_statistics_time_str_dict
    assert list(output_dict.keys()) == \
        ['House 1', 'House 2', 'Finite Commercial Producer', 'Commercial Energy Producer']
    assert list(output_dict['House 1'].keys()) == ['H1 DefinedLoad', 'H1 Storage1']
    counter = 0
    for house in ["House 1", "House 2"]:
        for device in output_dict[house]:
            for stats_name in EXPORT_DEVICE_VARIABLES:
                if stats_name in output_dict[house][device]:
                    counter += 1
                    assert len(list(output_dict[house][device][stats_name])) == 48
                    assert len(list(output_dict[house][device]["min_" + stats_name])) == 48
                    assert len(list(output_dict[house][device]["max_" + stats_name])) == 48
    assert counter == 12
