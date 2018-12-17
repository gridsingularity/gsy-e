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
from d3a.constants import TIME_FORMAT


@then('the storage devices buy and sell energy respecting the break even prices')
def check_storage_prices(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    storage = list(filter(lambda x: x.name == "H1 Storage1", house1.children))[0]
    trades_sold = []
    trades_bought = []
    for market in house1.past_markets:
        for trade in market.trades:
            if trade.seller in ["H1 Storage1"]:
                trades_sold.append(trade)
            elif trade.buyer in ["H1 Storage1"]:
                trades_bought.append(trade)
    assert all([trade.offer.price / trade.offer.energy >=
                list(storage.strategy.break_even.values())[0][1] for trade in trades_sold])
    assert all([trade.offer.price / trade.offer.energy <=
                list(storage.strategy.break_even.values())[0][0] for trade in trades_bought])
    assert len(trades_sold) > 0
    assert len(trades_bought) > 0


@then('the storage devices buy and sell energy respecting the hourly break even prices')
def step_impl(context):
    from d3a.setup.strategy_tests.storage_strategy_break_even_hourly import \
        break_even_profile, break_even_profile_2
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    for name, profile in [("H1 Storage1", break_even_profile),
                          ("H1 Storage2", break_even_profile_2)]:
        trades_sold = []
        trades_bought = []
        for market in house1.past_markets:
            slot = market.time_slot
            for trade in market.trades:
                if slot.hour in profile.keys():
                    if trade.seller == name:
                        trades_sold.append(trade)
                    elif trade.buyer == name:
                        trades_bought.append(trade)

        assert all([round((trade.offer.price / trade.offer.energy), 2) >=
                    round(profile[trade.time.hour][1], 2) for trade in trades_sold])
        assert all([round((trade.offer.price / trade.offer.energy), 2) <=
                    round(profile[trade.time.hour][0], 2) for trade in trades_bought])
        assert len(trades_sold) > 0


@then('the storage devices sell energy respecting the break even prices')
def check_storage_sell_prices(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    storage = list(filter(lambda x: x.name == "H1 Storage1", house1.children))[0]
    trades_sold = []
    trades_bought = []
    for market in house1.past_markets:
        for trade in market.trades:
            if trade.seller == storage.name:
                trades_sold.append(trade)
            elif trade.buyer == storage.name:
                trades_bought.append(trade)
    assert all([trade.offer.price / trade.offer.energy >=
                list(storage.strategy.break_even.values())[0][1] for trade in trades_sold])
    assert len(trades_sold) > 0


@then('the storage devices sell offer rate is based on it SOC')
def check_capacity_dependant_sell_rate(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    storage = list(filter(lambda x: x.name == "H1 Storage1", house1.children))[0]
    trades_sold = []
    for market in house1.past_markets:
        slot = market.time_slot
        for trade in market.trades:
            if trade.seller == storage.name:
                trades_sold.append(trade)
                trade_rate = round((trade.offer.price / trade.offer.energy), 2)
                break_even_sell = round(storage.strategy.break_even[
                                            slot.strftime(TIME_FORMAT)][1], 2)
                market_maker_rate = \
                    round(context.simulation.area.config.
                          market_maker_rate[slot.strftime(TIME_FORMAT)], 2)
                assert trade_rate >= break_even_sell
                assert trade_rate <= market_maker_rate
    assert len(trades_sold) == len(house1.past_markets)


@then("the storage offers and buys energy as expected at expected prices")
def check_custom_storage(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    storage = list(filter(lambda x: x.name == "H1 Storage1", house1.children))[0]
    price_dec_per_slot = 0.1 * int(context.simulation.simulation_config.slot_length.seconds /
                                   context.simulation.simulation_config.tick_length.seconds)
    trades_sold = []
    for market in house1.past_markets:
        slot = market.time_slot
        for id, offer in market.offers.items():
            if offer.seller in storage.name:
                assert isclose((offer.price / offer.energy),
                               context.simulation.simulation_config.
                               market_maker_rate[slot.strftime(TIME_FORMAT)] - price_dec_per_slot)
        for trade in market.trades:
            if trade.seller == storage.name:
                trades_sold.append(trade)
                trade_rate = round((trade.offer.price / trade.offer.energy), 2)
                break_even_sell = round(storage.strategy.break_even[
                                            slot.strftime(TIME_FORMAT)][1], 2)
                market_maker_rate = \
                    round(context.simulation.area.config.
                          market_maker_rate[slot.strftime(TIME_FORMAT)], 2)
                assert trade_rate >= break_even_sell
                assert trade_rate <= market_maker_rate
    assert len(trades_sold) > 0


@then("the SOC reaches 100% within the first {num_slots} market slots")
def check_soc(context, num_slots):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    storage = list(filter(lambda x: x.name == "H1 Storage1", house1.children))[0]
    list_of_charge = list(storage.strategy.state.charge_history.values())

    assert all([charge == 100.0 for charge in list_of_charge[int(num_slots)::]])
