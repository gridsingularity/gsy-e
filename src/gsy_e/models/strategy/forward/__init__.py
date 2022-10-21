from abc import ABC, abstractmethod
from typing import Union, TYPE_CHECKING, Dict

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.utils import str_to_pendulum_datetime
from pendulum import DateTime

from gsy_e.events import EventMixin, AreaEvent, MarketEvent
from gsy_e.models.base import AreaBehaviorBase
from gsy_e.models.strategy.forward.order_updater import OrderUpdater, OrderUpdaterParameters

if TYPE_CHECKING:
    from gsy_e.models.market.forward import ForwardMarketBase
    from gsy_e.models.state import StateInterface


ENABLE_EVENT_NAME = "enable"
DISABLE_EVENT_NAME = "disable"
POST_ORDER_EVENT_NAME = "post_order"
REMOVE_ORDER_EVENT_NAME = "remove_order"


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
        self._allowed_disable_events = [
            AreaEvent.ACTIVATE, MarketEvent.OFFER_TRADED, MarketEvent.BID_TRADED]
        self._order_updater_params = order_updater_parameters
        self._order_updaters = {}
        self._live_event_handler = ForwardLiveEvents(self)

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

    def event_tick(self):
        if self.enabled:
            self._update_open_orders()

    def event_market_cycle(self):
        self._delete_past_order_updaters()
        if self.enabled:
            self._post_orders_to_new_markets()

    @property
    def state(self) -> "StateInterface":
        """Get the state class of the strategy. Needs to be implemented by all strategies"""
        raise NotImplementedError

    def apply_live_event(self, event: Dict):
        self._live_event_handler.dispatch(event)


class ForwardLiveEvents:

    def __init__(self, strategy):
        self._strategy = strategy

    def dispatch(self, event: Dict):
        """Apply a live event to the strategy."""
        if event.get("type") not in self.available_events:
            self._strategy.log.error(
                "Invalid event (%s) for area %s.", event, self._strategy.area.name)

        if event.get("type") == ENABLE_EVENT_NAME:
            self.enable_event(event.get("args"))
        if event.get("type") == DISABLE_EVENT_NAME:
            self.disable_event()
        if event.get("type") == POST_ORDER_EVENT_NAME:
            self.post_order_event(event)
        if event.get("type") == REMOVE_ORDER_EVENT_NAME:
            self.remove_order_event(event)

    @property
    def available_events(self):
        """Return a list of events that the strategy can handle."""
        return [ENABLE_EVENT_NAME, DISABLE_EVENT_NAME,
                POST_ORDER_EVENT_NAME, REMOVE_ORDER_EVENT_NAME]

    def enable_event(self, event):
        # TODO: Reconfigure the orderupdater
        self._strategy.enabled = True

    def disable_event(self):
        self._strategy.enabled = True

    def post_order_event(self, event: Dict):
        args = event.get("args")
        accepted_params = ["market_type", "market_slot", "capacity_percent", "energy_rate"]
        if any(param not in args or not args[param] for param in accepted_params):
            self._strategy.log.error(
                "Parameters order_uuid, market_slot and market_type are obligatory "
                "for the post order live event (%s).", event)
            return

        market = self._strategy.area.forward_markets[AvailableMarketTypes(event["market_type"])]
        market_slot = str_to_pendulum_datetime(event["market_slot"])
        capacity_percent = event["capacity_percent"]
        energy_rate = event["energy_rate"]
        self._strategy.post_order(market, market_slot, capacity_percent, energy_rate)

    def remove_order_event(self, event: Dict):
        args = event.get("args")
        if "order_uuid" not in args or "market_slot" not in args or "market_type" not in args:
            self._strategy.log.error(
                "Parameters order_uuid, market_slot and market_type are obligatory "
                "for the remove order live event (%s).", event)
            return

        market = self._strategy.area.forward_markets[AvailableMarketTypes(event["market_type"])]
        market_slot = str_to_pendulum_datetime(event["market_slot"])
        order_uuid = event["order_uuid"]
        self._strategy.remove_order(market, market_slot, order_uuid)
