from d3a_interface.constants_limits import ConstSettings
from pendulum import duration

from d3a.constants import SettlementTemplateStrategiesConstants
from d3a.d3a_core.exceptions import MarketException
from d3a.models.strategy.update_frequency import TemplateStrategyBidUpdater, \
    TemplateStrategyOfferUpdater


def settlement_market_strategy_factory(
        initial_buying_rate: float = None, final_buying_rate: float = None,
        initial_selling_rate: float = None, final_selling_rate: float = None
):
    if initial_selling_rate is None:
        initial_selling_rate = SettlementTemplateStrategiesConstants.INITIAL_SELLING_RATE
    if final_selling_rate is None:
        final_selling_rate = SettlementTemplateStrategiesConstants.FINAL_SELLING_RATE
    if initial_buying_rate is None:
        initial_buying_rate = SettlementTemplateStrategiesConstants.INITIAL_BUYING_RATE
    if final_buying_rate is None:
        final_buying_rate = SettlementTemplateStrategiesConstants.FINAL_BUYING_RATE
    if ConstSettings.GeneralSettings.ENABLE_SETTLEMENT_MARKETS:
        return SettlementMarketStrategy(
            initial_buying_rate, final_buying_rate,
            initial_selling_rate, final_selling_rate)
    else:
        return SettlementMarketStrategyInterface(
            initial_buying_rate, final_buying_rate,
            initial_selling_rate, final_selling_rate
        )


class SettlementTemplateStrategyBidUpdater(TemplateStrategyBidUpdater):

    @staticmethod
    def get_all_markets(area):
        return area.settlement_markets.values()


class SettlementTemplateStrategyOfferUpdater(TemplateStrategyOfferUpdater):

    @staticmethod
    def get_all_markets(area):
        return area.settlement_markets.values()


class SettlementMarketStrategyInterface:
    def __init__(self, *args, **kwargs):
        pass

    def event_market_cycle(self, strategy):
        pass

    def event_tick(self, strategy):
        pass

    def event_bid_traded(self, strategy, market_id, bid_trade):
        pass

    def event_trade(self, strategy, market_id, trade):
        pass


class SettlementMarketStrategy(SettlementMarketStrategyInterface):

    def __init__(self,
                 initial_buying_rate, final_buying_rate,
                 initial_selling_rate, final_selling_rate):
        super().__init__()

        self._update_interval = SettlementTemplateStrategiesConstants.UPDATE_INTERVAL_MIN
        self.bid_updater = SettlementTemplateStrategyBidUpdater(
                initial_rate=initial_buying_rate,
                final_rate=final_buying_rate,
                fit_to_limit=True,
                energy_rate_change_per_update=None,
                update_interval=duration(minutes=self._update_interval),
                rate_limit_object=min)

        self.offer_updater = SettlementTemplateStrategyOfferUpdater(
                initial_rate=initial_selling_rate,
                final_rate=final_selling_rate,
                fit_to_limit=True,
                energy_rate_change_per_update=None,
                update_interval=duration(minutes=self._update_interval),
                rate_limit_object=max)

    def event_market_cycle(self, strategy):
        self.bid_updater.update_and_populate_price_settings(strategy.area)
        self.offer_updater.update_and_populate_price_settings(strategy.area)
        for market in strategy.area.settlement_markets.values():
            energy_deviation_kWh = strategy.state.get_unsettled_deviation_kWh(market.time_slot)

            if strategy.state.should_post_bid(market.time_slot):
                try:
                    strategy.post_first_bid(
                        market, energy_deviation_kWh * 1000.0,
                        self.bid_updater.initial_rate[market.time_slot]
                    )
                except MarketException:
                    pass

            if strategy.state.should_post_offer(market.time_slot):
                try:
                    strategy.post_first_offer(
                        market, energy_deviation_kWh,
                        self.offer_updater.initial_rate[market.time_slot]
                    )
                except MarketException:
                    pass

    def event_tick(self, strategy):
        self.bid_updater.increment_update_counter_all_markets(strategy)
        self.offer_updater.increment_update_counter_all_markets(strategy)
        """Update posted settlement bids and offers on market tick"""
        for market in strategy.area.settlement_markets.values():
            self.bid_updater.update(market, strategy)
            self.offer_updater.update(market, strategy)

    def _get_settlement_market_by_id(self, area, market_id):
        markets = [m for m in area.settlement_markets.values() if m.id == market_id]
        if not markets:
            return None
        return markets[0]

    def event_bid_traded(self, strategy, market_id, bid_trade):
        """Updates the unsettled deviation with the traded energy from the market"""
        market = self._get_settlement_market_by_id(strategy.area, market_id)
        if not market:
            return
        if bid_trade.offer_bid.buyer == strategy.owner.name:
            strategy.state.decrement_unsettled_deviation(
                bid_trade.offer_bid.energy, market.time_slot)

    def event_trade(self, strategy, market_id, trade):
        """Updates the unsettled deviation with the traded energy from the market"""
        market = self._get_settlement_market_by_id(strategy.area, market_id)
        if not market:
            return
        if trade.offer_bid.seller == strategy.owner.name:
            strategy.state.decrement_unsettled_deviation(
                trade.offer_bid.energy, market.time_slot)
