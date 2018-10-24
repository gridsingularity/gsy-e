from d3a.util import area_name_from_area_or_iaa_name
from d3a.area_statistics import get_area_type_string


def recursive_current_markets(area):
    if area.current_market is not None:
        yield area.current_market
        for child in area.children:
            yield from recursive_current_markets(child)


def primary_trades(markets):
    """
    We want to avoid counting trades between different areas multiple times
    (as they are represented as a chain of trades with IAAs). To achieve
    this, we skip all trades where the buyer is an IAA.
    """
    for market in markets:
        for trade in market.trades:
            if trade.buyer[:4] != 'IAA ':
                yield trade
    # TODO find a less hacky way to exclude trades with IAAs as buyers


def primary_unit_prices(markets):
    for trade in primary_trades(markets):
        yield trade.offer.price / trade.offer.energy


def total_avg_trade_price(markets):
    return (
        sum(trade.offer.price for trade in primary_trades(markets)) /
        sum(trade.offer.energy for trade in primary_trades(markets))
    )


def energy_bills(area, from_slot=None, to_slot=None):
    """
    Return a bill for each of area's children with total energy bought
    and sold (in kWh) and total money earned and spent (in cents).
    Compute bills recursively for children of children etc.
    """
    if not area.children:
        return None
    result = {child.name: dict(bought=0.0, sold=0.0,
                               spent=0.0, earned=0.0,
                               type=get_area_type_string(child))
              for child in area.children}
    for market in area.past_markets:
        slot = market.time_slot
        if (from_slot is None or slot >= from_slot) and (to_slot is None or slot < to_slot):
            for trade in market.trades:
                buyer = area_name_from_area_or_iaa_name(trade.buyer)
                seller = area_name_from_area_or_iaa_name(trade.offer.seller)
                if buyer in result:
                    result[buyer]['bought'] += trade.offer.energy
                    result[buyer]['spent'] += trade.offer.price
                if seller in result:
                    result[seller]['sold'] += trade.offer.energy
                    result[seller]['earned'] += trade.offer.price
    for child in area.children:
        child_result = energy_bills(child, from_slot, to_slot)
        if child_result is not None:
            result[child.name]['children'] = child_result
    return result
