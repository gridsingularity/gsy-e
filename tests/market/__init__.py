
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gsy_e.models.market.future import FutureMarkets


def count_orders_in_buffers(future_markets: "FutureMarkets", expected_count: int) -> None:
    """Count number of markets and orders created in buffers."""
    for buffer in [future_markets.slot_bid_mapping,
                   future_markets.slot_offer_mapping,
                   future_markets.slot_trade_mapping]:
        assert all(len(orders) == 1 for orders in buffer.values())
        assert len(buffer) == expected_count
    assert len(future_markets.bids) == expected_count
    assert len(future_markets.offers) == expected_count
    assert len(future_markets.trades) == expected_count
