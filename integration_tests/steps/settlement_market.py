from behave import then


@then("no settlement market is created")
def check_no_settlement_market(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    assert len(house.past_settlement_markets) == 0


@then("settlement markets are created")
def check_settlement_market(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    assert len(house.past_settlement_markets) == 23


@then("settlement market trades have been executed")
def check_settlement_market_trades(context):
    house = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    assert any(len(market.trades) > 0 for market in house.past_settlement_markets.values())
    assert all(
        25.0 <= t.trade_rate <= 30.0
        for market in house.past_settlement_markets.values()
        for t in market.trades
    )


@then("maximal one trade per market in the settlement market has been executed on grid level")
def check_settlement_market_trades_grid_level(context):
    grid_area = context.simulation.area
    assert any(len(market.trades) > 0 for market in grid_area.past_settlement_markets.values())
    assert all(0 <= len(market.trades) <= 1
               for market in grid_area.past_settlement_markets.values())
