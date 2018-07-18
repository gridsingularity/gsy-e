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
