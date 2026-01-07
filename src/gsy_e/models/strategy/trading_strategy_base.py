from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict

from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime, duration

from gsy_e.events import EventMixin
from gsy_e.models.base import AreaBehaviorBase
from gsy_e.models.strategy.order_updater import OrderUpdater, OrderUpdaterParameters
from gsy_e.models.strategy import _TradeLookerUpper

if TYPE_CHECKING:
    from gsy_e.models.strategy.state import StateInterface
    from gsy_e.models.market import MarketBase


class TradingStrategyBase(EventMixin, AreaBehaviorBase, ABC):
    """Base class for the new market strategies."""

    def __init__(
        self, order_updater_parameters: Dict[AvailableMarketTypes, OrderUpdaterParameters]
    ):

        super().__init__()
        self._order_updater_params: Dict[AvailableMarketTypes, OrderUpdaterParameters] = (
            order_updater_parameters
        )
        self._order_updaters: Dict["MarketBase", Dict[DateTime, OrderUpdater]] = {}

    def serialize(self):
        """Serialize strategy parameters."""
        return {}

    @staticmethod
    def deserialize_args(constructor_args: Dict) -> Dict:
        """Deserialize the constructor arguments for the OrderUpdaterParameters."""
        if "order_updater_params" in constructor_args:
            constructor_args["order_updater_params"] = {
                AvailableMarketTypes(market_type): OrderUpdaterParameters(
                    duration(minutes=updater_params[0]), updater_params[1], updater_params[2]
                )
                for market_type, updater_params in constructor_args["order_updater_params"].items()
            }
        return constructor_args

    def _update_grid_fees_in_order_updater_params(self):
        for order_updater_params in self._order_updater_params.values():
            order_updater_params.grid_fee = self.owner.get_path_to_root_fees()

    def _order_updater_for_market_slot_exists(self, market: "MarketBase", market_slot):
        if market not in self._order_updaters:
            return False
        return market_slot in self._order_updaters[market]

    def _update_open_orders(self):
        for market, market_slot_updater_dict in self._order_updaters.items():
            for market_slot, updater in market_slot_updater_dict.items():
                if updater.is_time_for_update(self.area.now):
                    self.remove_open_orders(market, market_slot)
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
    def remove_open_orders(self, market: "MarketBase", market_slot: DateTime):
        """Remove the open orders on the markets."""
        raise NotImplementedError

    @abstractmethod
    def post_order(
        self, market: "MarketBase", market_slot: DateTime, order_rate: float = None, **kwargs
    ):
        """Post orders to the markets that just opened."""
        raise NotImplementedError

    @abstractmethod
    def remove_order(self, market: "MarketBase", market_slot: DateTime, order_uuid: str):
        """Remove order from the selected market."""
        raise NotImplementedError

    def event_offer_traded(self, *, market_id, trade):
        """Method triggered by the MarketEvent.OFFER_TRADED event."""

    def event_bid_traded(self, *, market_id, bid_trade):
        """Method triggered by the MarketEvent.BID_TRADED event."""

    def event_tick(self):
        self._update_open_orders()

    def event_market_cycle(self):
        self._delete_past_order_updaters()

    @property
    def state(self) -> "StateInterface":
        """Get the state class of the strategy. Needs to be implemented by all strategies"""
        raise NotImplementedError

    @property
    def trades(self):
        """Return the tracked trades of the strategy"""
        return _TradeLookerUpper(self.owner.name)
