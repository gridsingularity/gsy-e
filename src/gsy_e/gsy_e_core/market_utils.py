"""
Has to stay in this package because of otherwise circualr imports
"""
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import BidOfferMatchAlgoEnum
from pendulum import DateTime


class MarketCounter:
    """Base class for market counters"""

    def __init__(self, clearing_interval: int):
        self._last_time_dispatched = None
        self.clearing_interval = clearing_interval

    def is_time_for_clearing(self, current_time: DateTime) -> bool:
        """Return if it is time for clearing according to self.clearing_interval."""
        if not self._last_time_dispatched:
            self._last_time_dispatched = current_time
            return True
        duration_in_min = (current_time - self._last_time_dispatched).minutes
        if duration_in_min >= self.clearing_interval:
            self._last_time_dispatched = current_time
            return True
        return False


class FutureMarketCounter(MarketCounter):
    """Hold a time counter for the future market.

    In the future market, we only want to clear in a predefined interval.
    """
    def __init__(self):
        super().__init__(
            clearing_interval=ConstSettings.FutureMarketSettings.
            FUTURE_MARKET_CLEARING_INTERVAL_MINUTES)


def is_time_slot_in_past_markets(time_slot: DateTime, current_time_slot: DateTime):
    """Checks if the time_slot should be in the area.past_markets."""
    if ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
        return (time_slot < current_time_slot.subtract(
            hours=ConstSettings.SettlementMarketSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS))
    return time_slot < current_time_slot


def is_external_matching_enabled():
    """Checks if the bid offer match type is set to external
    Returns True if both are matched
    """
    return (ConstSettings.MASettings.BID_OFFER_MATCH_TYPE ==
            BidOfferMatchAlgoEnum.EXTERNAL.value)


class ExternalTickCounter:
    """External tick counter."""

    def __init__(self, ticks_per_slot: int, dispatch_frequency_percent: int):
        self._dispatch_tick_frequency = int(
            ticks_per_slot *
            (dispatch_frequency_percent / 100)
        )

    def is_it_time_for_external_tick(self, current_tick_in_slot: int) -> bool:
        """Boolean return if time for external tick."""
        return current_tick_in_slot % self._dispatch_tick_frequency == 0
