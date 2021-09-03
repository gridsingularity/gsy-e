"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from enum import Enum
from logging import getLogger
from typing import Dict

from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime

from d3a import constants

log = getLogger(__name__)


class MarketClassType(Enum):
    SPOT = 0
    BALANCING = 1
    SETTLEMENT = 2


class BaseRotator:
    """Base implementation of the market rotator."""

    def rotate(self, current_time_slot: DateTime):
        pass


class DefaultMarketRotator(BaseRotator):
    """Deal with market rotation."""

    def __init__(self, markets: Dict, past_markets: Dict) -> None:
        self.markets = markets
        self.past_markets = past_markets

    def rotate(self, current_time_slot: DateTime) -> None:
        """Move markets to past and delete old past markets."""
        self._move_markets_to_past(self.markets, self.past_markets, current_time_slot)
        self._delete_past_markets(self.past_markets, current_time_slot)

    @staticmethod
    def _is_it_time_to_delete_past_market(current_time_slot: DateTime,
                                          time_slot: DateTime) -> bool:
        """Check if the past market for time_slot is ready to be deleted."""

        if constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            return False
        else:
            if ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
                # if the settlement markets are enabled, the same amount as the active
                # settlement markets has to be kept in the past_market buffer
                return (time_slot < current_time_slot.subtract(
                    hours=ConstSettings.SettlementMarketSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS))
            else:
                return time_slot < current_time_slot.subtract(
                    minutes=GlobalConfig.slot_length.total_minutes())

    def _is_it_time_to_rotate_market(self, current_time_slot: DateTime,
                                     time_slot: DateTime) -> bool:
        """Check if it is time to move market for time_slot into past markets."""
        return time_slot < current_time_slot

    def _move_markets_to_past(self, markets: Dict, past_markets: Dict,
                              current_time_slot: DateTime) -> None:
        """Move markets to self.past_markets."""
        market_slots_to_be_cycled = [
            time_slot for time_slot in markets.keys()
            if self._is_it_time_to_rotate_market(current_time_slot, time_slot)]
        for time_slot in market_slots_to_be_cycled:
            market = markets.pop(time_slot)
            market.readonly = True
            past_markets[time_slot] = market
            log.debug("Moving %s to past.", past_markets[time_slot])

    def _delete_past_markets(self, market_dict: Dict, current_time_slot: DateTime) -> None:
        """Delete the unneeded markets from self.past_markets."""
        market_slots_to_be_deleted = [
            time_slot for time_slot in market_dict.keys()
            if self._is_it_time_to_delete_past_market(current_time_slot, time_slot)]
        for time_slot in market_slots_to_be_deleted:
            self._delete_market_and_all_attributes(market_dict, time_slot)

    @staticmethod
    def _delete_market_and_all_attributes(market_buffer: Dict, time_slot: DateTime) -> None:
        """Delete market and all its attributes from the provided market_buffer.
        When searching for a memory leak, we found out, that garbage collector does not delete
        all attributes of the markets correctly. One possible explanation is that these
        attributes are also referenced between each other and on other places in which case
        the GC will not delete it from the memory."""

        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            market_buffer[time_slot].redis_api.stop()
        del market_buffer[time_slot].offers
        del market_buffer[time_slot].trades
        del market_buffer[time_slot].offer_history
        del market_buffer[time_slot].notification_listeners
        del market_buffer[time_slot].bids
        del market_buffer[time_slot].bid_history
        del market_buffer[time_slot].traded_energy
        del market_buffer[time_slot]


class SettlementMarketRotator(DefaultMarketRotator):
    """Deal with market rotation of settlement markets."""
    @staticmethod
    def _is_it_time_to_delete_past_market(current_time_slot: DateTime,
                                          time_slot: DateTime) -> bool:
        """Check if the past market for time_slot is ready to be deleted."""
        return (time_slot < current_time_slot.subtract(
            hours=ConstSettings.SettlementMarketSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS,
            minutes=GlobalConfig.slot_length.total_minutes()))

    def _is_it_time_to_rotate_market(self, current_time_slot: DateTime,
                                     time_slot: DateTime) -> bool:
        """ Check if it is time to move market for time_slot into past markets. """
        return (time_slot < current_time_slot.subtract(
            hours=ConstSettings.SettlementMarketSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS))
