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
def step_impl(context, start_hour, end_hour):
    start_hour = int(start_hour)
    end_hour = int(end_hour)
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    assert all(len(market.trades) == 0
               for market in house1.past_markets
               if start_hour <= market.time_slot.hour < end_hour)
