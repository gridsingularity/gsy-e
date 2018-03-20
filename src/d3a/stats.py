from itertools import chain
from statistics import mean


def recursive_current_markets(area):
    if area.current_market is not None:
        yield area.current_market
        for child in area.children:
            yield from recursive_current_markets(child)


def total_avg_trade_price(markets):
    """
    Average trade price over all trades in a set of markets. We want
    to avoid counting trades between different areas multiple times
    (as they are represented as a chain of trades with IAAs). To achieve
    this, we skip all trades where the buyer is an IAA.
    """
    return mean(
        trade.offer.price
        for trade in chain(*(market.trades for market in markets))
        if trade.buyer[:4] != "IAA "
    )
    # TODO find a less hacky way to exclude trades with IAAs as buyers
