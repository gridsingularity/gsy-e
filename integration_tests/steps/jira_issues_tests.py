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
from pendulum import today
import os
from gsy_e.gsy_e_core.util import d3a_path
from gsy_e.constants import TIME_ZONE
from gsy_e.gsy_e_core.export import EXPORT_DEVICE_VARIABLES
from gsy_framework.sim_results.market_price_energy_day import MarketPriceEnergyDay
from gsy_framework.sim_results.bills import CumulativeBills
from gsy_framework.sim_results.cumulative_grid_trades import CumulativeGridTrades


def get_areas_from_2_house_grid(context):
    def filter_ma(x):
        return x.name == "House 1" or \
               x.name == "House 2" or \
               x.name == "Grid"

    return list(filter(filter_ma,
                       context.simulation.area.children))


@then('average trade rate is constant for every market slot for all markets')
def average_trade_rate_constant(context):
    areas = get_areas_from_2_house_grid(context)

    for area in areas:
        trade_rates = [
            trade.offer_bid.energy_rate
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

    assert all(
        [trade.offer_bid.energy_rate < 16.99 for trade in storage_trades])


@then('on every market slot there should be matching trades on grid and house markets')
def check_matching_trades(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    for time_slot, core_stats in context.raw_sim_data.items():
        grid_trades = core_stats[context.name_uuid_map['Grid']]['trades']
        house_trades = core_stats[context.name_uuid_map['House 1']]['trades']
        assert len(grid_trades) == len(house_trades)
        assert all(
            any(t['energy'] == th['energy'] and t['buyer'] == th['seller'] for th in house_trades)
            for t in grid_trades)


@then('pv produces the same energy on each corresponding time slot regardless of the day')
def pv_produces_same_amount_of_energy_day(context):
    house2 = [child for child in context.simulation.area.children if child.name == "House 2"][0]

    for base_market in house2.past_markets:
        time_slot = base_market.time_slot
        same_time_markets = [market for market in house2.past_markets
                             if market.time_slot.hour == time_slot.hour and
                             market.time_slot.minute == time_slot.minute]
        same_time_markets_energy = [sum(trade.offer_bid.energy
                                        for trade in market.trades
                                        if trade.seller == "H2 PV")
                                    for market in same_time_markets]
        assert all(isclose(same_time_markets_energy[0], energy)
                   for energy in same_time_markets_energy)


def _assert_sum_of_energy_is_same_for_same_time(area, load_name):
    for base_market in area.past_markets:
        time_slot = base_market.time_slot
        same_time_markets = [market for market in area.past_markets
                             if market.time_slot.hour == time_slot.hour and
                             market.time_slot.minute == time_slot.minute]
        same_time_markets_energy = [sum(trade.offer_bid.energy
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
        total_energy = sum(trade.offer_bid.energy
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
    max_rate = load1.strategy.bid_update.final_rate

    for market in grid.past_markets:
        assert len(market.trades) == 1
        assert all(t.seller == "Commercial Energy Producer" for t in market.trades)
        assert all(t.buyer == "House 1" for t in market.trades)
        assert all(
            isclose(trade.offer_bid.energy_rate, max_rate[market.time_slot])
            for trade in market.trades)

    for market in house1.past_markets:
        assert len(market.trades) == 1
        assert all(t.seller == "House 1" for t in market.trades)
        assert all(t.buyer == "H1 General Load" for t in market.trades)
        assert all(
            isclose(trade.offer_bid.energy_rate, max_rate[market.time_slot])
            for trade in market.trades)


@then('the Load of House 1 should only buy energy from MarketAgent between 5:00 and 8:00')
def house1_load_only_from_ma(context):
    from gsy_framework.constants_limits import ConstSettings
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    load1 = [child for child in house1.children if child.name == "H1 General Load"][0]

    for market in load1.past_markets:
        if not 5 <= market.time_slot.hour < 8:
            continue

        assert len(market.trades) == 1
        assert market.trades[0].offer_bid.seller == \
            ConstSettings.GeneralSettings.ALT_PRICING_MARKET_MAKER_NAME


@then('the Commercial Producer should never sell energy')
def commercial_never_trades(context):
    commercial = [child for child in context.simulation.area.children
                  if child.name == "Commercial Energy Producer"][0]
    assert all(len(m.trades) == 0 for m in commercial.past_markets)


@then('the device statistics are correct')
def device_statistics(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    output_dict = raw_results["device_statistics"]
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


@then("an AreaException is raised")
def area_exception_is_raised(context):
    from gsy_e.gsy_e_core.exceptions import AreaException
    assert type(context.sim_error) == AreaException


@then('trades happen when the load seeks energy')
def trades_happen(context):
    trade_count = 0
    for market in context.simulation.area.past_markets:
        if len(market.trades) != 0:
            assert today(tz=TIME_ZONE).add(hours=8) <= market.time_slot \
                   <= today(tz=TIME_ZONE).add(hours=16)
            trade_count += 1
    assert trade_count == 9


@given('the file {setup_json} is used for the area setup')
def json_setup_file(context, setup_json):
    os.environ["D3A_SETUP_PATH"] = os.path.join(d3a_path, 'setup', setup_json)


@then('the DSO doesnt pay the grid fee of the Grid, but {child_market}')
def dso_pays_certain_price(context, child_market):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    bills = raw_results["bills"]

    child_market_spent = bills["Grid"][child_market]["spent"]
    dso_earned_on_grid = bills["Grid"]["DSO"]["earned"]
    grid_fees = bills["Grid"]["Accumulated Trades"]["market_fee"]
    assert isclose(child_market_spent-dso_earned_on_grid, grid_fees)
    assert bills["DSO"]["earned"] == dso_earned_on_grid
    assert bills["Grid"]["Accumulated Trades"]["spent"] == child_market_spent
    assert bills["Grid"]["Accumulated Trades"]["earned"] == dso_earned_on_grid
    assert isclose(bills["Grid"]["Accumulated Trades"]["total_cost"],
                   bills["Grid"]["Accumulated Trades"]["spent"] -
                   bills["Grid"]["Accumulated Trades"]["earned"])


@then('the storage decreases bid rate until final buying rate')
def storage_decreases_bid_rate(context):
    for market in context.simulation.area.past_markets:
        assert len(market.trades) == 1
        trade = market.trades[0]
        trade_rate = trade.offer_bid.energy_rate
        assert isclose(trade_rate, 15)


@then('cumulative grid trades correctly reports the external trade')
def area_external_trade(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    cumulative_trade = raw_results["cumulative_grid_trades"]
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    cal_cum_trades = CumulativeGridTrades.generate_cumulative_grid_trades_target_area(
            house1.uuid, {'cumulative_grid_trades': cumulative_trade.get(house1.uuid, None)}
    )
    ext_trade = sum(info['bars'][0]['energy']
                    for info in cal_cum_trades[house1.uuid]
                    if info['areaName'] == "External Trades")
    assert isclose(ext_trade, -1 * 0.666, rel_tol=1e-05)


@then('we test the min/max/avg trade and devices bill')
def check_area_trade_and_bill(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    count = 0
    mped = MarketPriceEnergyDay(should_export_plots=False)
    for time_slot, core_stats in context.raw_sim_data.items():
        mped.update(context.area_tree_summary_data, core_stats, time_slot)
        count += 1
        area_data = mped.redis_output[context.name_uuid_map['Grid']]
        assert area_data['price-energy-day'][0]['min_price'] == 0.35
        assert area_data['price-energy-day'][0]['max_price'] == 0.35
        assert area_data['price-energy-day'][0]['grid_fee_constant'] == 0.05
    assert count == 24
    cb = CumulativeBills()
    for time_slot, core_stats in context.raw_sim_data.items():
        cb.update(context.area_tree_summary_data, core_stats, time_slot)
    assert isclose(cb.cumulative_bills_results[context.name_uuid_map['Market Maker']]['earned'],
                   0.72)
    assert isclose(cb.cumulative_bills_results[context.name_uuid_map['Load']]['spent_total'], 0.84)


@given("raising exceptions when running the simulation is disabled")
def do_not_raise_exceptions(context):
    context.raise_exception_when_running_sim = False
