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
from abc import ABC
from collections import OrderedDict
from logging import getLogger
from typing import Dict, List, TYPE_CHECKING

from d3a import constants
from d3a.d3a_core.util import is_timeslot_in_simulation_duration
from d3a.models.market import GridFee, Market
from d3a.models.market.balancing import BalancingMarket
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.market.two_sided import TwoSidedMarket
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime

if TYPE_CHECKING:
    from d3a.models.area import Area

log = getLogger(__name__)


class RotatorInterface(ABC):
    """Market rotator interface"""

    def rotate(self, current_time_slot):
        pass


class MarketRotatorBase(RotatorInterface):
    """Deal with market rotation."""

    def __init__(self, markets: Dict, past_markets: Dict):
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
            if ConstSettings.GeneralSettings.ENABLE_SETTLEMENT_MARKETS:
                return (time_slot < current_time_slot.subtract(
                    hours=ConstSettings.GeneralSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS))
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
        move_market_slots = [
            time_slot for time_slot in markets.keys()
            if self._is_it_time_to_rotate_market(current_time_slot, time_slot)]
        for time_slot in move_market_slots:
            market = markets.pop(time_slot)
            market.readonly = True
            past_markets[time_slot] = market
            log.debug("Moving %s to past.", past_markets[time_slot])

    def _delete_past_markets(self, market_dict: Dict, current_time_slot: DateTime) -> None:
        """Delete the unneeded markets from self.past_markets."""
        delete_market_slots = [
            time_slot for time_slot in market_dict.keys()
            if self._is_it_time_to_delete_past_market(current_time_slot, time_slot)]
        for time_slot in delete_market_slots:
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


class SlotMarketRotator(MarketRotatorBase):
    """Deal with market rotation of slot markets."""


class BalancingMarketRotator(MarketRotatorBase):
    """Deal with market rotation of balancing markets."""


class SettlementMarketRotator(MarketRotatorBase):
    """Deal with market rotation of settlement markets."""
    @staticmethod
    def _is_it_time_to_delete_past_market(current_time_slot: DateTime,
                                          time_slot: DateTime) -> bool:
        """Check if the past market for time_slot is ready to be deleted."""
        return (time_slot < current_time_slot.subtract(
            hours=ConstSettings.GeneralSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS,
            minutes=GlobalConfig.slot_length.total_minutes()))

    def _is_it_time_to_rotate_market(self, current_time_slot: DateTime,
                                     time_slot: DateTime) -> bool:
        """ Check if it is time to move market for time_slot into past markets. """
        return (time_slot < current_time_slot.subtract(
            hours=ConstSettings.GeneralSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS))


class AreaMarkets:
    """Class that holds all markets for areas."""

    def __init__(self, area_log):
        self.log = area_log
        # Children trade in `markets`
        self.markets:  Dict[DateTime, Market] = OrderedDict()
        self.balancing_markets:  Dict[DateTime, BalancingMarket] = OrderedDict()
        self.settlement_markets: Dict[DateTime, Market] = OrderedDict()
        # Past markets:
        self.past_markets:  Dict[DateTime, Market] = OrderedDict()
        self.past_balancing_markets:  Dict[DateTime, BalancingMarket] = OrderedDict()
        self.past_settlement_markets: Dict[DateTime, Market] = OrderedDict()
        self.indexed_future_markets = {}

        self.slot_market_rotator = RotatorInterface()
        self.balancing_market_rotator = RotatorInterface()
        self.settlement_market_rotator = RotatorInterface()

    def activate_market_rotators(self):
        """The user specific ConstSettings are not available when the class is constructed,
        so we need to have a two-stage initialization here."""
        self.slot_market_rotator = SlotMarketRotator(self.markets, self.past_markets)
        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self.balancing_market_rotator = (
                BalancingMarketRotator(self.balancing_markets, self.past_balancing_markets))
        if ConstSettings.GeneralSettings.ENABLE_SETTLEMENT_MARKETS:
            self.settlement_market_rotator = (
                SettlementMarketRotator(self.settlement_markets, self.past_settlement_markets))

    @property
    def future_spot_markets(self) -> List:
        """Return all future markets in a list."""
        return list(self.markets.values())

    def _update_indexed_future_markets(self) -> None:
        """Update the indexed_future_markets mapping."""
        self.indexed_future_markets = {m.id: m for m in self.future_spot_markets}

    def rotate_markets(self, current_time: DateTime) -> None:
        """Deal with market rotation of different types."""
        self.slot_market_rotator.rotate(current_time)
        self.balancing_market_rotator.rotate(current_time)
        self.settlement_market_rotator.rotate(current_time)

        self._update_indexed_future_markets()

    @staticmethod
    def _select_market_class(is_spot_market: bool) -> Market:
        """Select market class dependent on the global config."""
        if is_spot_market:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                return OneSidedMarket
            elif ConstSettings.IAASettings.MARKET_TYPE == 2:
                return TwoSidedMarket
        else:
            return BalancingMarket

    def create_future_markets(self, current_time: DateTime,
                              is_spot_market: bool, area: "Area") -> bool:
        """Create future markets according to the market count."""
        markets = self.markets if is_spot_market else self.balancing_markets
        market_class = self._select_market_class(is_spot_market)

        changed = False
        for offset in (area.config.slot_length * i
                       for i in range(area.config.market_count)):
            time_slot = current_time + offset
            if time_slot not in markets:
                markets[time_slot] = self._create_market(market_class, time_slot, area,
                                                         is_spot_market)
                changed = True
                self.log.trace("Adding {t:{format}} market".format(
                    t=time_slot,
                    format="%H:%M" if area.config.slot_length.seconds > 60 else "%H:%M:%S"
                ))
        self._update_indexed_future_markets()
        return changed

    def create_settlement_market(self, time_slot: DateTime, area: "Area") -> None:
        """Create a new settlement market."""
        self.settlement_markets[time_slot] = (
            self._create_market(market_class=self._select_market_class(is_spot_market=True),
                                time_slot=time_slot,
                                area=area, is_spot_market=True))
        self.log.trace(
            "Adding Settlement {t:{format}} market".format(
                t=time_slot,
                format="%H:%M" if area.config.slot_length.seconds > 60 else "%H:%M:%S"))

    @staticmethod
    def _create_market(market_class: Market,
                       time_slot: DateTime, area: "Area", is_spot_market: bool) -> Market:
        """Create market for specific time_slot and market type."""
        market = market_class(
            time_slot=time_slot,
            bc=area.bc,
            notification_listener=area.dispatcher.broadcast_callback,
            grid_fee_type=area.config.grid_fee_type,
            grid_fees=GridFee(grid_fee_percentage=area.grid_fee_percentage,
                              grid_fee_const=area.grid_fee_constant),
            name=area.name,
            in_sim_duration=is_timeslot_in_simulation_duration(area.config, time_slot)
        )

        area.dispatcher.create_area_agents(is_spot_market, market)
        return market
