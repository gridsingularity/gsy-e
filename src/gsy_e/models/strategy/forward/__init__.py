from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime, duration

from gsy_e.events import EventMixin
from gsy_e.models.base import AreaBehaviorBase
from gsy_e.models.strategy.forward.live_event_handler import ForwardLiveEvents
from gsy_e.models.strategy.forward.order_updater import OrderUpdater, OrderUpdaterParameters

if TYPE_CHECKING:
    from gsy_e.models.market.forward import ForwardMarketBase
    from gsy_e.models.state import StateInterface


class ForwardStrategyBase(EventMixin, AreaBehaviorBase, ABC):
    """Base class for the forward market strategies."""
    def __init__(self,
                 order_updater_parameters: Dict[AvailableMarketTypes, OrderUpdaterParameters]):
        assert ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS is True
        assert (
            0.0 <=
            sum(params.capacity_percent for params in order_updater_parameters.values()) <=
            100.0)
        super().__init__()
        self._create_order_updater = ConstSettings.ForwardMarketSettings.FULLY_AUTO_TRADING
        self._order_updater_params: Dict[AvailableMarketTypes,
                                         OrderUpdaterParameters] = order_updater_parameters
        self._order_updaters = {}
        self._live_event_handler = ForwardLiveEvents(self)

    @staticmethod
    def deserialize_args(constructor_args: Dict) -> Dict:
        """Deserialize the constructor arguments for the forward classes."""
        if "order_updater_params" in constructor_args:
            constructor_args["order_updater_params"] = {
                AvailableMarketTypes(market_type): OrderUpdaterParameters(
                    duration(minutes=updater_params[0]), updater_params[1],
                    updater_params[2], updater_params[3]
                )
                for market_type, updater_params in constructor_args["order_updater_params"].items()
            }
        return constructor_args

    def _order_updater_for_market_slot_exists(self, market: "ForwardMarketBase", market_slot):
        if market.id not in self._order_updaters:
            return False
        return market_slot in self._order_updaters[market.id]

    def _update_open_orders(self):
        for market, market_slot_updater_dict in self._order_updaters.items():
            for market_slot, updater in market_slot_updater_dict.items():
                if updater.is_time_for_update(self.area.now):
                    self.remove_open_orders(market, market_slot)
                    self.post_order(market, market_slot)

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
                    self._order_updaters[market][market_slot] = OrderUpdater(
                        self._order_updater_params[market_type],
                        market_parameters
                    )
                    self.post_order(market, market_slot)

    def _delete_past_order_updaters(self):
        for market_object, market_slot_updater_dict in self._order_updaters.items():
            slots_to_delete = []
            for market_slot in market_slot_updater_dict.keys():
                market_params = market_object.get_market_parameters_for_market_slot(market_slot)
                if not market_params:
                    slots_to_delete.append(market_slot)
                    continue
                if market_params.closing_time <= self.area.now:
                    slots_to_delete.append(market_slot)
            for slot in slots_to_delete:
                market_slot_updater_dict.pop(slot)

    @abstractmethod
    def remove_open_orders(self, market: "ForwardMarketBase", market_slot: DateTime):
        """Remove the open orders on the forward markets."""
        raise NotImplementedError

    @abstractmethod
    def post_order(self, market: "ForwardMarketBase", market_slot: DateTime,
                   order_rate: float = None, capacity_percent: float = None):
        """Post orders to the forward markets that just opened."""
        raise NotImplementedError

    @abstractmethod
    def remove_order(self, market: "ForwardMarketBase", market_slot: DateTime, order_uuid: str):
        """Remove order from the selected forward market."""
        raise NotImplementedError

    def event_offer_traded(self, *, market_id, trade):
        """Method triggered by the MarketEvent.OFFER_TRADED event."""

    def event_bid_traded(self, *, market_id, bid_trade):
        """Method triggered by the MarketEvent.BID_TRADED event."""

    @property
    def fully_automated_trading(self):
        """Is the strategy in fully automated trading mode."""
        return self._create_order_updater

    def event_tick(self):
        self._update_open_orders()

    def event_market_cycle(self):
        self._delete_past_order_updaters()
        if self.fully_automated_trading:
            self._post_orders_to_new_markets()

    @property
    def state(self) -> "StateInterface":
        """Get the state class of the strategy. Needs to be implemented by all strategies"""
        raise NotImplementedError

    def apply_live_event(self, event: Dict):
        """Apply the incoming live event to the strategy."""
        self._live_event_handler.dispatch(event)
