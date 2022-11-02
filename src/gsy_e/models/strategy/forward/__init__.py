from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Union, TYPE_CHECKING, Dict

from gsy_e.events import EventMixin, AreaEvent, MarketEvent
from gsy_e.models.base import AreaBehaviorBase
from gsy_e.models.strategy.forward.order_updater import OrderUpdater, OrderUpdaterParameters
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.live_events.b2b import LiveEventArgsValidator, B2BLiveEvents
from gsy_framework.utils import str_to_pendulum_datetime
from pendulum import DateTime, duration

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
        self.enabled = True
        self._create_order_updater = ConstSettings.ForwardMarketSettings.FULLY_AUTO_TRADING
        self._allowed_disable_events = [
            AreaEvent.ACTIVATE, MarketEvent.OFFER_TRADED, MarketEvent.BID_TRADED]
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

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        """Dispatches the events received by the strategy to the respective methods."""
        if self.enabled or event_type in self._allowed_disable_events:
            super().event_listener(event_type, **kwargs)

    def event_offer_traded(self, *, market_id, trade):
        """Method triggered by the MarketEvent.OFFER_TRADED event."""

    def event_bid_traded(self, *, market_id, bid_trade):
        """Method triggered by the MarketEvent.BID_TRADED event."""

    @property
    def fully_automated_trading(self):
        """Is the strategy in fully automated trading mode."""
        return self.enabled and self._create_order_updater

    def event_tick(self):
        if self.enabled:
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


class ForwardLiveEvents:
    """Handle live events for the forward strategies."""

    def __init__(self, strategy):
        self._strategy = strategy

    def dispatch(self, event: Dict):
        """Apply a live event to the strategy."""
        if not B2BLiveEvents.is_supported_event(event.get("type")):
            self._strategy.log.error(
                "Invalid event (%s) for area %s.", event, self._strategy.area.name)
            return

        if event.get("type") == B2BLiveEvents.ENABLE_TRADING_EVENT_NAME:
            self.auto_trading_event(event.get("args"))
        if event.get("type") == B2BLiveEvents.DISABLE_TRADING_EVENT_NAME:
            self.stop_auto_trading_event(event.get("args"))
        if event.get("type") == B2BLiveEvents.POST_ORDER_EVENT_NAME:
            self.post_order_event(event)
        if event.get("type") == B2BLiveEvents.REMOVE_ORDER_EVENT_NAME:
            self.remove_order_event(event)

    def auto_trading_event(self, event):
        """
        Enable energy trading, and create order updater for all open markets between the start and
        end time.
        """
        args = event.get("args")
        if not LiveEventArgsValidator(self._strategy.log).validate_start_trading_event_args(args):
            return

        market_type = AvailableMarketTypes(args["market_type"])
        start_time = str_to_pendulum_datetime(args["start_time"])
        end_time = str_to_pendulum_datetime(args["end_time"])
        capacity_percent = args["capacity_percent"]
        energy_rate = args["energy_rate"]
        market = self._strategy.area.forward_markets[market_type]

        for slot in market.market_time_slots:
            if not start_time <= slot <= end_time:
                continue

            updater = self._strategy._order_updaters[market].get(slot)
            if updater:
                market.remove_open_orders(slot)

            market_parameters = market.get_market_parameters_for_market_slot(slot)

            order_updater_params = deepcopy(self._strategy._order_updater_params[market_type])
            order_updater_params.capacity_percent = capacity_percent
            order_updater_params.final_rate = energy_rate
            order_updater_params.initial_rate = min(
                order_updater_params.initial_rate, energy_rate)

            self._strategy._order_updaters[market][slot] = OrderUpdater(
                order_updater_params, market_parameters)
            self._strategy.post_order(market, slot)

    def stop_auto_trading_event(self, event: Dict):
        """Apply stop automatic trading event to the strategy."""
        self.remove_order_event(event)

    def post_order_event(self, event: Dict):
        """Apply post order / manual trading event to the strategy."""
        args = event.get("args")
        if not LiveEventArgsValidator(self._strategy.log).validate_start_trading_event_args(args):
            return

        market = self._strategy.area.forward_markets[AvailableMarketTypes(args["market_type"])]
        start_time = str_to_pendulum_datetime(args["start_time"])
        end_time = str_to_pendulum_datetime(args["end_time"])
        capacity_percent = args["capacity_percent"]
        energy_rate = args["energy_rate"]
        for slot in market.market_time_slots:
            if start_time <= slot <= end_time:
                self._strategy.post_order(market, slot, capacity_percent, energy_rate)

    def remove_order_event(self, event: Dict):
        """Apply remove order event to the strategy."""
        args = event.get("args")
        if not LiveEventArgsValidator(self._strategy.log).validate_stop_trading_event_args(args):
            return

        market = self._strategy.area.forward_markets[AvailableMarketTypes(args["market_type"])]
        start_time = str_to_pendulum_datetime(args["start_time"])
        end_time = str_to_pendulum_datetime(args["end_time"])
        for slot in market.market_time_slots:
            if not start_time <= slot <= end_time:
                continue
            updater = self._strategy._order_updaters[market].get(slot)
            if updater:
                market.remove_open_orders(slot)
                self._strategy._order_updaters[market].pop(slot)
