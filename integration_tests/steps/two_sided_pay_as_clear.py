from math import isclose
from behave import then


@then('all trades are equal to market_clearing_rate')
def test_traded_energy_rate(context):
    grid = context.simulation.area
    for child in grid.children:
        for a, b in child.dispatcher.interarea_agents.items():
            for c in b:
                for d in c.engines:
                    for trade in d.markets.source.trades:
                        if len(d.clearing_rate) > 0:
                            assert any([isclose((trade.offer.price/trade.offer.energy), rate)
                                        for rate in d.clearing_rate])
