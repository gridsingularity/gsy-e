from behave import then
from math import isclose
from d3a.export_unmatched_loads import export_unmatched_loads


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
            for slot, market in area.past_markets.items()
            for trade in market.trades
        ]

        assert all(isclose(t, trade_rates[0]) for t in trade_rates[1:])


@then('there are no trades with the same seller and buyer name')
def same_seller_buyer_name_check(context):
    areas = get_areas_from_2_house_grid(context)

    trades = [
        trade
        for area in areas
        for slot, market in area.past_markets.items()
        for trade in market.trades
    ]

    assert all(trade.buyer != trade.seller for trade in trades)


@then('storage buys energy from the commercial producer')
def storage_commercial_trades(context):
    house1 = [child for child in context.simulation.area.children
              if child.name == "House 1"][0]

    storage_trades = [
        trade
        for slot, market in house1.past_markets.items()
        for trade in market.trades
        if trade.buyer == "H1 Storage1"
    ]

    commercial_trades = [
        trade
        for slot, market in context.simulation.area.past_markets.items()
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
        for slot, market in storage.past_markets.items()
        for trade in market.trades
        if trade.buyer == "H1 Storage1"
    ]

    assert all([trade.offer.price / trade.offer.energy < 16.99 for trade in storage_trades])


@then('on every market slot there should be matching trades on grid and house markets')
def check_matching_trades(context):
    house1 = [child for child in context.simulation.area.children if child.name == "House 1"][0]
    grid = context.simulation.area

    for timeslot, market in grid.markets.items():
        assert timeslot in house1.markets.keys()
        grid_trades = grid.markets[timeslot].trades
        house_trades = house1.markets[timeslot].trades
        assert len(grid_trades) == len(house_trades)
        assert all(
            any(t.offer.energy == th.offer.energy and t.buyer == th.seller for th in house_trades)
            for t in grid_trades)


@then('there should be no unmatched loads')
def no_unmatched_loads(context):
    unmatched = export_unmatched_loads(context.simulation.area)
    assert unmatched["unmatched_load_count"] == 0


@then('pv produces the same energy on each corresponding time slot regardless of the day')
def pv_produces_same_amount_of_energy_day(context):
    house2 = [child for child in context.simulation.area.children if child.name == "House 2"][0]

    for timeslot, base_market in house2.past_markets.items():

        same_time_markets = [market for time, market in house2.past_markets.items()
                             if time.hour == timeslot.hour and time.minute == timeslot.minute]
        same_time_markets_energy = [sum(trade.offer.energy
                                        for trade in market.trades
                                        if trade.seller == "H2 PV")
                                    for market in same_time_markets]
        assert all(isclose(same_time_markets_energy[0], energy)
                   for energy in same_time_markets_energy)


def _assert_sum_of_energy_is_same_for_same_time(area, load_name):
    for timeslot, base_market in area.past_markets.items():
        same_time_markets = [market for time, market in area.past_markets.items()
                             if time.hour == timeslot.hour and time.minute == timeslot.minute]
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
    for timeslot, market in area.past_markets.items():
        total_energy = sum(trade.offer.energy
                           for trade in market.trades if trade.buyer == device.name)
        if timeslot.hour not in device.strategy.hrs_of_day:
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
