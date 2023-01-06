from typing import TYPE_CHECKING, Dict

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from pendulum import duration

from gsy_e.models.strategy.forward.live_event_handler import ForwardLiveEvents
from gsy_e.models.strategy.forward.order_updater import (
    ForwardOrderUpdater, ForwardOrderUpdaterParameters)
from gsy_e.models.strategy.trading_strategy_base import TradingStrategyBase

if TYPE_CHECKING:
    from gsy_e.models.strategy.state import StateInterface


class ForwardStrategyBase(TradingStrategyBase):
    """Base class for the forward market strategies."""
    def __init__(self,
                 order_updater_parameters: Dict[
                     AvailableMarketTypes, ForwardOrderUpdaterParameters]):
        assert ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS is True
        assert (
            0.0 <=
            sum(params.capacity_percent for params in order_updater_parameters.values()) <=
            100.0)

        super().__init__(order_updater_parameters=order_updater_parameters)

        self._create_order_updater = ConstSettings.ForwardMarketSettings.FULLY_AUTO_TRADING
        self._live_event_handler = ForwardLiveEvents(self)

    @staticmethod
    def deserialize_args(constructor_args: Dict) -> Dict:
        """Deserialize the constructor arguments for the forward classes."""
        if "order_updater_params" in constructor_args:
            constructor_args["order_updater_params"] = {
                AvailableMarketTypes(market_type): ForwardOrderUpdaterParameters(
                    duration(minutes=updater_params[0]), updater_params[1],
                    updater_params[2], updater_params[3]
                )
                for market_type, updater_params in constructor_args["order_updater_params"].items()
            }
        return constructor_args

    def _post_orders_to_new_markets(self):
        forward_markets = self.area.forward_markets
        for market_type, market in forward_markets.items():
            if market not in self._order_updaters:
                self._order_updaters[market] = {}

            for market_slot in market.market_time_slots:
                market_parameters = market.get_market_parameters_for_market_slot(market_slot)
                if (market_parameters.closing_time <= market_parameters.opening_time or
                        market_parameters.closing_time <= self.area.now):
                    continue
                if not self._order_updater_for_market_slot_exists(market, market_slot):
                    self._order_updaters[market][market_slot] = ForwardOrderUpdater(
                        self._order_updater_params[market_type],
                        market_parameters
                    )
                    self.post_order(market, market_slot)

    @property
    def fully_automated_trading(self):
        """Is the strategy in fully automated trading mode."""
        return self._create_order_updater

    def event_market_cycle(self):
        super().event_market_cycle()
        if self.fully_automated_trading:
            self._post_orders_to_new_markets()

    @property
    def state(self) -> "StateInterface":
        """Get the state class of the strategy. Needs to be implemented by all strategies"""
        raise NotImplementedError

    def apply_live_event(self, event: Dict):
        """Apply the incoming live event to the strategy."""
        self._live_event_handler.dispatch(event)
