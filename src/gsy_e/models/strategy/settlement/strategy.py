"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange
This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not,
see <http://www.gnu.org/licenses/>.
"""
from typing import Optional, Dict, Iterable, TYPE_CHECKING

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Trade
from gsy_framework.utils import format_datetime
from pendulum import duration

from gsy_e.constants import SettlementTemplateStrategiesConstants
from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.update_frequency import (TemplateStrategyBidUpdater,
                                                    TemplateStrategyOfferUpdater)

if TYPE_CHECKING:
    from gsy_e.models.area import Area
    from gsy_e.models.strategy import BidEnabledStrategy


class SettlementTemplateStrategyBidUpdater(TemplateStrategyBidUpdater):
    """Version of TemplateStrategyBidUpdater class for settlement markets"""

    def __init__(self, initial_rate, final_rate, update_interval):
        super().__init__(
            initial_rate=initial_rate,
            final_rate=final_rate,
            fit_to_limit=True,
            energy_rate_change_per_update=None,
            update_interval=update_interval,
            rate_limit_object=min)
        self.set_parameters(initial_rate=initial_rate, final_rate=final_rate,
                            update_interval=update_interval)

    @staticmethod
    def get_all_markets(area: "Area") -> Iterable[MarketBase]:
        return area.settlement_markets.values()

    @staticmethod
    def _get_all_time_slots(area):
        return area.settlement_markets.keys()


class SettlementTemplateStrategyOfferUpdater(TemplateStrategyOfferUpdater):
    """Version of TemplateStrategyOfferUpdater class for settlement markets"""

    def __init__(self, initial_rate, final_rate, update_interval):
        super().__init__(
            initial_rate=initial_rate,
            final_rate=final_rate,
            fit_to_limit=True,
            energy_rate_change_per_update=None,
            update_interval=update_interval,
            rate_limit_object=max)
        self.set_parameters(initial_rate=initial_rate, final_rate=final_rate,
                            update_interval=update_interval)

    @staticmethod
    def get_all_markets(area: "Area") -> Iterable[MarketBase]:
        return area.settlement_markets.values()

    @staticmethod
    def _get_all_time_slots(area):
        return area.settlement_markets.keys()


class SettlementMarketStrategyInterface:
    """Dummy/empty class that does not provide concrete implementation of the methods.
    Is needed in order to disable the implementation of the settlement market strategy
    when settlement markets are disabled by configuration."""
    def __init__(self, *args, **kwargs):
        pass

    def event_market_cycle(self, strategy: "BidEnabledStrategy"):
        pass

    def event_tick(self, strategy: "BidEnabledStrategy"):
        pass

    def event_bid_traded(self, strategy: "BidEnabledStrategy", market_id: str, bid_trade: Trade):
        pass

    def event_offer_traded(self, strategy: "BidEnabledStrategy", market_id: str, trade: Trade):
        pass

    def get_unsettled_deviation_dict(self, _) -> Dict:
        return {}


class SettlementMarketStrategy(SettlementMarketStrategyInterface):
    def __init__(self,
                 initial_buying_rate: float, final_buying_rate: float,
                 initial_selling_rate: float, final_selling_rate: float):
        """
        Manages bid/offer trading strategy for the settlement markets, for a single asset.
        Args:
            initial_buying_rate: Initial rate of the settlement bids
            final_buying_rate: Final rate of the settlement bids
            initial_selling_rate: Initial rate of the settlement offers
            final_selling_rate: Final rate of the settlement offers
        """
        super().__init__()

        self._update_interval = SettlementTemplateStrategiesConstants.UPDATE_INTERVAL_MIN
        self.bid_updater = SettlementTemplateStrategyBidUpdater(
                initial_rate=initial_buying_rate,
                final_rate=final_buying_rate,
                update_interval=duration(minutes=self._update_interval))

        self.offer_updater = SettlementTemplateStrategyOfferUpdater(
                initial_rate=initial_selling_rate,
                final_rate=final_selling_rate,
                update_interval=duration(minutes=self._update_interval))

    def event_market_cycle(self, strategy: "BidEnabledStrategy") -> None:
        """
        Should be called by the event_market_cycle of the asset strategy class, posts
        settlement bids and offers on markets that do not have posted bids and offers yet
        Args:
            strategy: Strategy object of the asset

        Returns: None

        """
        self.bid_updater.update_and_populate_price_settings(strategy.area)
        self.offer_updater.update_and_populate_price_settings(strategy.area)
        for market in strategy.area.settlement_markets.values():
            energy_deviation_kWh = strategy.state.get_unsettled_deviation_kWh(market.time_slot)

            if strategy.state.can_post_settlement_bid(market.time_slot):
                try:
                    strategy.post_first_bid(
                        market, energy_deviation_kWh * 1000.0,
                        self.bid_updater.initial_rate[market.time_slot]
                    )
                except MarketException:
                    pass

            if strategy.state.can_post_settlement_offer(market.time_slot):
                try:
                    strategy.post_first_offer(
                        market, energy_deviation_kWh,
                        self.offer_updater.initial_rate[market.time_slot]
                    )
                except MarketException:
                    pass
        # has to be called in order not to update the initial bid/offer in the first tick
        self.bid_updater.increment_update_counter_all_markets(strategy)
        self.offer_updater.increment_update_counter_all_markets(strategy)

    def event_tick(self, strategy: "BidEnabledStrategy") -> None:
        """
        Update posted settlement bids and offers on market tick.
        Order matters here:
            - FIRST: the bids and offers need to be updated (update())
            - SECOND: the update counter has to be increased (increment_update_counter_all_markets)
        Args:
            strategy: Strategy object of the asset

        Returns: None

        """
        for market in strategy.area.settlement_markets.values():
            self.bid_updater.update(market, strategy)
            self.offer_updater.update(market, strategy)

        self.bid_updater.increment_update_counter_all_markets(strategy)
        self.offer_updater.increment_update_counter_all_markets(strategy)

    @staticmethod
    def _get_settlement_market_by_id(strategy: "BidEnabledStrategy",
                                     market_id: str) -> Optional["MarketBase"]:
        markets = [market for market in strategy.area.settlement_markets.values()
                   if market.id == market_id]
        if not markets:
            return None
        assert len(markets) == 1
        return markets[0]

    def event_bid_traded(self, strategy: "BidEnabledStrategy", market_id: str,
                         bid_trade: Trade) -> None:
        """
        Updates the unsettled deviation with the traded energy from the market
        Args:
            strategy: Strategy object of the asset
            market_id: Id of the market that the trade took place
            bid_trade: Trade object

        Returns: None

        """
        market = self._get_settlement_market_by_id(strategy, market_id)
        if not market:
            return

        if not bid_trade.is_bid_trade:
            return

        if bid_trade.match_details["bid"].buyer.name == strategy.owner.name:
            strategy.state.decrement_unsettled_deviation(
                bid_trade.traded_energy, market.time_slot)

    def event_offer_traded(self, strategy: "BidEnabledStrategy",
                           market_id: str, trade: Trade) -> None:
        """
        Updates the unsettled deviation with the traded energy from the market
        Args:
            strategy: Strategy object of the asset
            market_id: Id of the market that the trade took place
            trade: Trade object

        Returns: None

        """
        market = self._get_settlement_market_by_id(strategy, market_id)
        if not market:
            return

        if not trade.is_offer_trade:
            return

        if trade.match_details["offer"].seller.name == strategy.owner.name:
            strategy.state.decrement_unsettled_deviation(
                trade.traded_energy, market.time_slot)

    def get_unsettled_deviation_dict(self, strategy: "BidEnabledStrategy") -> Dict:
        return {
            "unsettled_deviation_kWh": {
                format_datetime(time_slot):
                    strategy.state.get_signed_unsettled_deviation_kWh(time_slot)
                for time_slot in strategy.area.settlement_markets
            }
        }


def settlement_market_strategy_factory(
        initial_buying_rate: float = SettlementTemplateStrategiesConstants.INITIAL_BUYING_RATE,
        final_buying_rate: float = SettlementTemplateStrategiesConstants.FINAL_BUYING_RATE,
        initial_selling_rate: float = SettlementTemplateStrategiesConstants.INITIAL_SELLING_RATE,
        final_selling_rate: float = SettlementTemplateStrategiesConstants.FINAL_SELLING_RATE
) -> SettlementMarketStrategyInterface:
    """
    Factory method for creating the settlement market trading strategy. Creates an object of a
    class with empty implementation if the settlement market is disabled, with the real
    implementation otherwise
    Args:
        initial_buying_rate: Initial rate of the settlement bids
        final_buying_rate: Final rate of the settlement bids
        initial_selling_rate: Initial rate of the settlement offers
        final_selling_rate: Final rate of the settlement offers

    Returns: Settlement strategy object

    """
    if ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
        return SettlementMarketStrategy(
            initial_buying_rate, final_buying_rate,
            initial_selling_rate, final_selling_rate)
    else:
        return SettlementMarketStrategyInterface(
            initial_buying_rate, final_buying_rate,
            initial_selling_rate, final_selling_rate
        )
