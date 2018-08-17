from behave import then
from math import isclose


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
