"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.
This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not,
see <http://www.gnu.org/licenses/>.
"""
from typing import TYPE_CHECKING, List, Union, Optional

from gsy_framework.constants_limits import ConstSettings
from pendulum import duration, DateTime

from gsy_e.constants import FutureTemplateStrategiesConstants
from gsy_e.models.base import AssetType
from gsy_e.models.strategy.update_frequency import (
    TemplateStrategyBidUpdater, TemplateStrategyOfferUpdater, TemplateStrategyUpdaterInterface)

if TYPE_CHECKING:
    from gsy_e.models.area import Area
    from gsy_e.models.strategy import BaseStrategy
    from gsy_e.models.market.future import FutureMarkets
    from gsy_framework.data_classes import Offer, Bid


class FutureTemplateStrategyBidUpdater(TemplateStrategyBidUpdater):
    """Version of TemplateStrategyBidUpdater class for future markets"""

    @property
    def _time_slot_duration_in_seconds(self) -> int:
        return ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS * 60 * 60

    @staticmethod
    def get_all_markets(area: "Area") -> List["FutureMarkets"]:
        """Override to return list of future markets"""
        return [area.future_markets]

    @staticmethod
    def _get_all_time_slots(area: "Area") -> List[DateTime]:
        """Override to return all future market available time slots"""
        if not area.future_markets:
            return []
        return area.future_markets.market_time_slots

    def time_for_price_update(self, strategy: "BaseStrategy", time_slot: DateTime) -> bool:
        """Check if the prices of bids/offers should be updated."""
        return (
                self._elapsed_seconds(strategy.area)
                - self.market_slot_added_time_mapping[time_slot] >= (
                        self.update_interval.seconds * self.update_counter[time_slot]))

    def update(self, market: "FutureMarkets", strategy: "BaseStrategy") -> None:
        """Update the price of existing bids to reflect the new rates."""
        for time_slot in strategy.area.future_markets.market_time_slots:
            if self.time_for_price_update(strategy, time_slot):
                if strategy.are_bids_posted(market.id, time_slot):
                    strategy.update_bid_rates(market, self.get_updated_rate(time_slot), time_slot)

    def delete_past_state_values(self, current_market_time_slot: DateTime) -> None:
        """Delete irrelevant values from buffers for unneeded markets."""
        self._delete_market_slot_data(current_market_time_slot)


class FutureTemplateStrategyOfferUpdater(TemplateStrategyOfferUpdater):
    """Version of TemplateStrategyOfferUpdater class for future markets"""

    @property
    def _time_slot_duration_in_seconds(self) -> int:
        return ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS * 60 * 60

    @staticmethod
    def get_all_markets(area: "Area") -> List["FutureMarkets"]:
        """Override to return list of future markets"""
        return [area.future_markets]

    @staticmethod
    def _get_all_time_slots(area: "Area") -> List[DateTime]:
        """Override to return all future market available time slots"""
        if not area.future_markets:
            return []
        return area.future_markets.market_time_slots

    def time_for_price_update(self, strategy: "BaseStrategy", time_slot: DateTime) -> bool:
        """Check if the prices of bids/offers should be updated."""
        return (
                self._elapsed_seconds(strategy.area)
                - self.market_slot_added_time_mapping[time_slot] >= (
                        self.update_interval.seconds * self.update_counter[time_slot]))

    def update(self, market: "FutureMarkets", strategy: "BaseStrategy") -> None:
        """Update the price of existing offers to reflect the new rates."""
        for time_slot in strategy.area.future_markets.market_time_slots:
            if self.time_for_price_update(strategy, time_slot):
                if strategy.are_offers_posted(market.id):
                    strategy.update_offer_rates(
                        market, self.get_updated_rate(time_slot), time_slot)

    def delete_past_state_values(self, current_market_time_slot: DateTime) -> None:
        """Delete irrelevant values from buffers for unneeded markets."""
        self._delete_market_slot_data(current_market_time_slot)


class FutureMarketStrategyInterface:
    """Dummy/empty class that does not provide concrete implementation of the methods.
    Is needed in order to disable the implementation of the future market strategy
    when future markets are disabled by configuration."""
    def __init__(self, *args, **kwargs):
        pass

    def event_market_cycle(self, strategy: "BaseStrategy") -> None:
        """Base class method for handling the market cycle"""

    def event_tick(self, strategy: "BaseStrategy") -> None:
        """Base class method for handling the tick"""

    def update_and_populate_price_settings(self, strategy: "BaseStrategy") -> None:
        """Base class method for updating/populating price settings"""

    def delete_past_state_values(self, current_market_time_slot: DateTime) -> None:
        """Base class method for deleting the state of past or spot markets."""


def future_strategy_bid_updater_factory(
        initial_buying_rate: float, final_buying_rate: float, asset_type: AssetType
) -> Union[TemplateStrategyUpdaterInterface, FutureTemplateStrategyBidUpdater]:
    """
    Factory method for the bid updater, disables the updater if the strategy does not support bids
    """
    _update_interval = FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN
    if asset_type in [AssetType.CONSUMER, AssetType.PROSUMER]:
        return FutureTemplateStrategyBidUpdater(
            initial_rate=initial_buying_rate,
            final_rate=final_buying_rate,
            fit_to_limit=True,
            energy_rate_change_per_update=None,
            update_interval=duration(minutes=_update_interval),
            rate_limit_object=min)
    return TemplateStrategyUpdaterInterface()


def future_strategy_offer_updater_factory(
        initial_selling_rate: float, final_selling_rate: float, asset_type: AssetType
) -> Union[TemplateStrategyUpdaterInterface, FutureTemplateStrategyOfferUpdater]:
    """
    Factory method for the offer updater, disables the updater if the strategy does not support
    offers
    """
    _update_interval = FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN
    if asset_type in [AssetType.PRODUCER, AssetType.PROSUMER]:
        return FutureTemplateStrategyOfferUpdater(
            initial_rate=initial_selling_rate,
            final_rate=final_selling_rate,
            fit_to_limit=True,
            energy_rate_change_per_update=None,
            update_interval=duration(minutes=_update_interval),
            rate_limit_object=max)
    return TemplateStrategyUpdaterInterface()


class FutureMarketStrategy(FutureMarketStrategyInterface):
    """Manages bid/offer trading strategy for the future markets, for a single asset."""
    def __init__(self, asset_type: AssetType,
                 initial_buying_rate: float, final_buying_rate: float,
                 initial_selling_rate: float, final_selling_rate: float):
        # pylint: disable=too-many-arguments
        """
        Args:
            initial_buying_rate: Initial rate of the future bids
            final_buying_rate: Final rate of the future bids
            initial_selling_rate: Initial rate of the future offers
            final_selling_rate: Final rate of the future offers
        """
        super().__init__()
        self._offer_updater = future_strategy_offer_updater_factory(
            initial_selling_rate, final_selling_rate, asset_type
        )

        self._bid_updater = future_strategy_bid_updater_factory(
            initial_buying_rate, final_buying_rate, asset_type
        )

    def update_and_populate_price_settings(self, strategy):
        """
        Update and populate the price settings of the bid / offer updaters. Should be called
        on every market cycle, and during the live event handling process of each strategy.
        """
        self._bid_updater.update_and_populate_price_settings(strategy.area)
        self._offer_updater.update_and_populate_price_settings(strategy.area)

    def event_market_cycle(self, strategy: "BaseStrategy") -> None:
        """
        Should be called by the event_market_cycle of the asset strategy class, posts
        settlement bids and offers on markets that do not have posted bids and offers yet
        Args:
            strategy: Strategy object of the asset

        Returns: None

        """
        if not strategy.area.future_markets:
            return
        self.update_and_populate_price_settings(strategy)
        for time_slot in strategy.area.future_markets.market_time_slots:
            if strategy.asset_type == AssetType.CONSUMER:
                required_energy_kWh = strategy.state.get_energy_requirement_Wh(time_slot) / 1000.0
                self._post_consumer_first_bid(strategy, time_slot, required_energy_kWh)
            elif strategy.asset_type == AssetType.PRODUCER:
                available_energy_kWh = strategy.state.get_available_energy_kWh(time_slot)
                self._post_producer_first_offer(strategy, time_slot, available_energy_kWh)
            elif strategy.asset_type == AssetType.PROSUMER:
                available_energy_sell_kWh = strategy.state.get_available_energy_to_sell_kWh(
                    time_slot)
                available_energy_buy_kWh = strategy.state.get_available_energy_to_buy_kWh(
                    time_slot)
                first_offer = self._post_producer_first_offer(
                    strategy, time_slot, available_energy_sell_kWh)
                first_bid = self._post_consumer_first_bid(
                    strategy, time_slot, available_energy_buy_kWh)
                if first_offer:
                    strategy.state.register_energy_from_posted_offer(first_offer.energy, time_slot)
                if first_bid:
                    strategy.state.register_energy_from_posted_bid(first_bid.energy, time_slot)

            else:
                assert False, ("Strategy %s has to be producer or consumer to be able to "
                               "participate in the future market.", strategy.owner.name)

    def _post_consumer_first_bid(
            self, strategy: "BaseStrategy", time_slot: DateTime,
            available_buy_energy_kWh: float) -> Optional["Bid"]:
        if available_buy_energy_kWh <= 0.0:
            return None
        if strategy.get_posted_bids(strategy.area.future_markets, time_slot):
            return None
        bid = strategy.post_bid(
            market=strategy.area.future_markets,
            energy=available_buy_energy_kWh,
            price=available_buy_energy_kWh * self._bid_updater.get_updated_rate(time_slot),
            time_slot=time_slot,
            replace_existing=False
        )
        # update_counter has to be increased because the first price counts as a price update
        # pylint: disable=no-member
        self._bid_updater.increment_update_counter(strategy, time_slot)
        return bid

    def _post_producer_first_offer(
            self, strategy: "BaseStrategy", time_slot: DateTime,
            available_sell_energy_kWh: float) -> Optional["Offer"]:
        if available_sell_energy_kWh <= 0.0:
            return None
        if strategy.get_posted_offers(strategy.area.future_markets, time_slot):
            return None
        offer = strategy.post_offer(
            market=strategy.area.future_markets,
            replace_existing=False,
            energy=available_sell_energy_kWh,
            price=available_sell_energy_kWh * self._offer_updater.get_updated_rate(time_slot),
            time_slot=time_slot
        )
        # update_counter has to be increased because the first price counts as a price update
        # pylint: disable=no-member
        self._offer_updater.increment_update_counter(strategy, time_slot)
        return offer

    def event_tick(self, strategy: "BaseStrategy") -> None:
        """
        Update posted settlement bids and offers on market tick.
        Order matters here:
            - FIRST: the bids and offers need to be updated (update())
            - SECOND: the update counter has to be increased (increment_update_counter_all_markets)
        Args:
            strategy: Strategy object of the asset

        Returns: None

        """
        if not strategy.area.future_markets:
            return
        self._bid_updater.update(strategy.area.future_markets, strategy)
        self._offer_updater.update(strategy.area.future_markets, strategy)

        self._bid_updater.increment_update_counter_all_markets(strategy)
        self._offer_updater.increment_update_counter_all_markets(strategy)

    def delete_past_state_values(self, current_market_time_slot: DateTime) -> None:
        self._bid_updater.delete_past_state_values(current_market_time_slot)
        self._offer_updater.delete_past_state_values(current_market_time_slot)


def future_market_strategy_factory(asset_type: AssetType) -> FutureMarketStrategyInterface:
    """
    Factory method for creating the future market trading strategy. Creates an object of a
    class with empty implementation if the future market is disabled, with the real
    implementation otherwise

    Returns: Future strategy object

    """
    initial_buying_rate = FutureTemplateStrategiesConstants.INITIAL_BUYING_RATE
    final_buying_rate = FutureTemplateStrategiesConstants.FINAL_BUYING_RATE
    initial_selling_rate = FutureTemplateStrategiesConstants.INITIAL_SELLING_RATE
    final_selling_rate = FutureTemplateStrategiesConstants.FINAL_SELLING_RATE
    if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS > 0:
        return FutureMarketStrategy(
            asset_type, initial_buying_rate, final_buying_rate,
            initial_selling_rate, final_selling_rate)
    return FutureMarketStrategyInterface(
        asset_type, initial_buying_rate, final_buying_rate,
        initial_selling_rate, final_selling_rate
    )
