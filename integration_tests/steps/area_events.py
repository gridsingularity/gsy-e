from behave import then


def one_or_none_trade_before_or_after(context, hour, is_before, nr_expected_trades):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    for market in house1.past_markets:
        if is_before and market.time_slot.hour >= hour:
            continue
        elif not is_before and market.time_slot.hour < hour:
            continue
        assert len(market.trades) == nr_expected_trades


@then('trades occur before {}:00')
def trades_before(context, hour):
    hour = int(hour)
    one_or_none_trade_before_or_after(context, hour, is_before=True, nr_expected_trades=1)


@then('no trades occur after {}:00')
def no_trades_after(context, hour):
    hour = int(hour)
    one_or_none_trade_before_or_after(context, hour, is_before=False, nr_expected_trades=0)


@then('trades occur after {}:00')
def trades_after(context, hour):
    hour = int(hour)
    one_or_none_trade_before_or_after(context, hour, is_before=False, nr_expected_trades=1)


@then('no trades occur between {start_hour}:00 and {end_hour}:00')
def no_trades_between(context, start_hour, end_hour):
    start_hour = int(start_hour)
    end_hour = int(end_hour)
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    assert all(len(market.trades) == 0
               for market in house1.past_markets
               if start_hour <= market.time_slot.hour < end_hour)


@then('load and battery use energy from grid before {hour}:00')
def load_uses_battery_before(context, hour):
    hour = int(hour)
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))

    for market in house1.past_markets:
        if market.time_slot.hour >= hour:
            continue
        assert len(market.trades) == 2
        assert all(t.seller == "IAA House 1" for t in market.trades)


@then('load and battery use energy from grid after {hour}:00')
def load_uses_battery_after(context, hour):
    hour = int(hour)
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))

    for market in house1.past_markets:
        if market.time_slot.hour < hour:
            continue
        assert len(market.trades) == 1
        assert all(t.seller == "IAA House 1" and t.buyer == "H1 General Load"
                   for t in market.trades)


@then('battery does not charge between {start_hour}:00 and {end_hour}:00')
def battery_not_charge(context, start_hour, end_hour):
    start_hour = int(start_hour)
    end_hour = int(end_hour)
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))

    for market in house1.past_markets:
        if not start_hour < market.time_slot.hour < end_hour:
            continue
        assert len(market.trades) == 1
        assert market.trades[0].seller == "H1 Storage1" and \
            market.trades[0].buyer == "H1 General Load"


@then('load consumes less than {energy} kWh between {start_time}:00 and {end_time}:00')
def load_consumes_less_than_between(context, energy, start_time, end_time):
    start_time = int(start_time)
    end_time = int(end_time)
    energy = float(energy)

    for market in context.simulation.area.past_markets:
        if not start_time <= market.time_slot.hour < end_time:
            continue
        assert market.trades[0].seller == "IAA House 1" and \
            market.trades[0].buyer == "Grid Load"
        assert market.trades[0].offer.energy <= energy


@then('load consumes {energy} kWh before {hour}:00')
def load_consumes_before(context, energy, hour):
    hour = int(hour)
    energy = float(energy)

    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))

    for market in house1.past_markets:
        if market.time_slot.hour >= hour:
            continue
        assert len(market.trades) == 1
        assert market.trades[0].seller == "IAA House 1" and \
            market.trades[0].buyer == "H1 General Load"
        assert market.trades[0].offer.energy == energy


@then('load consumes {energy} kWh between {start_time}:00 and {end_time}:00')
def load_consumes_between(context, energy, start_time, end_time):
    start_time = int(start_time)
    end_time = int(end_time)
    energy = float(energy)

    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))

    for market in house1.past_markets:
        if not start_time <= market.time_slot.hour < end_time:
            continue
        assert len(market.trades) == 1
        assert market.trades[0].seller == "IAA House 1" and \
            market.trades[0].buyer == "H1 General Load"
        assert market.trades[0].offer.energy == energy
