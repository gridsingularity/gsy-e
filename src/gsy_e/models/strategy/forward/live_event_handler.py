from copy import deepcopy
from typing import Dict
from pendulum import duration

from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.live_events.b2b import LiveEventArgsValidator, B2BLiveEvents
from gsy_framework.utils import str_to_pendulum_datetime

from gsy_e.models.strategy.forward.order_updater import ForwardOrderUpdater


class ForwardValidator:
    """Contain decorators that validate the start / stop trading live event arguments."""

    # pylint: disable=protected-access

    @staticmethod
    def start_trading(func):
        """Validate that the start trading live event contains all the required arguments."""
        return ForwardValidator._validate_method(func, start_trading=True)

    @staticmethod
    def stop_trading(func):
        """Validate that the stop trading live event contains all the required arguments."""
        return ForwardValidator._validate_method(func, start_trading=False)

    @staticmethod
    def _validate_method(func, start_trading=True):
        def validate_event(*method_args):
            self, args = method_args
            if start_trading and not LiveEventArgsValidator(
                self._strategy.log.error
            ).are_start_trading_event_args_valid(args):
                return
            if not start_trading and not LiveEventArgsValidator(
                self._strategy.log.error
            ).are_stop_trading_event_args_valid(args):
                return
            func(self, args)

        return validate_event


class ForwardLiveEvents:
    """Handle live events for the forward strategies."""

    # pylint: disable=protected-access

    def __init__(self, strategy):
        self._strategy = strategy

    def dispatch(self, event: Dict):
        """Apply a live event to the strategy."""
        if not B2BLiveEvents.is_supported_event(event.get("type")):
            self._strategy.log.error(
                "Invalid event (%s) for area %s.", event, self._strategy.area.name
            )
            return

        if event.get("type") == B2BLiveEvents.ENABLE_TRADING_EVENT_NAME:
            self._auto_trading_event(event.get("args"))
        if event.get("type") == B2BLiveEvents.DISABLE_TRADING_EVENT_NAME:
            self._stop_auto_trading_event(event.get("args"))
        if event.get("type") == B2BLiveEvents.POST_ORDER_EVENT_NAME:
            self._post_order_event(event.get("args"))
        if event.get("type") == B2BLiveEvents.REMOVE_ORDER_EVENT_NAME:
            self._remove_order_event(event.get("args"))

    @ForwardValidator.start_trading
    def _auto_trading_event(self, args: Dict):
        """
        Enable energy trading, and create order updater for all open markets between the start and
        end time.
        """
        market_type = AvailableMarketTypes(args["market_type"])
        start_time = str_to_pendulum_datetime(args["start_time"])
        end_time = str_to_pendulum_datetime(args["end_time"])
        capacity_percent = args["capacity_percent"]
        energy_rate = args["energy_rate"]
        market = self._strategy.area.forward_markets[market_type]

        for slot in market.market_time_slots:
            if not start_time <= slot <= end_time:
                continue

            if market not in self._strategy._order_updaters:
                self._strategy._order_updaters[market] = {}
            updater = self._strategy._order_updaters[market].get(slot)
            if updater:
                market.remove_open_orders(slot)

            market_parameters = market.get_market_parameters_for_market_slot(slot)

            order_updater_params = deepcopy(self._strategy._order_updater_params[market_type])
            # temporary fix, until https://github.com/python-pendulum/pendulum/issues/870 is fixed
            if market_type == AvailableMarketTypes.MONTH_FORWARD:
                order_updater_params.update_interval = duration(weeks=1)
            order_updater_params.capacity_percent = capacity_percent
            order_updater_params.final_rate = energy_rate

            # Clamping the value between the initial / final rate for the specified market in
            # order to always fall in the accepted energy rate range.
            order_updater_params.initial_rate = max(
                min(order_updater_params.initial_rate, energy_rate),
                order_updater_params.final_rate,
            )

            self._strategy._order_updaters[market][slot] = ForwardOrderUpdater(
                order_updater_params, market_parameters
            )
            self._strategy.post_order(market, slot)

    @ForwardValidator.stop_trading
    def _stop_auto_trading_event(self, args: Dict):
        """Apply stop automatic trading event to the strategy."""
        self._remove_order_event(args)

    @ForwardValidator.start_trading
    def _post_order_event(self, args: Dict):
        """Apply post order / manual trading event to the strategy."""
        market = self._strategy.area.forward_markets[AvailableMarketTypes(args["market_type"])]
        start_time = str_to_pendulum_datetime(args["start_time"])
        end_time = str_to_pendulum_datetime(args["end_time"])
        capacity_percent = args["capacity_percent"]
        energy_rate = args["energy_rate"]
        for slot in market.market_time_slots:
            if start_time <= slot <= end_time:
                self._strategy.post_order(
                    market, slot, energy_rate, capacity_percent=capacity_percent
                )

    @ForwardValidator.stop_trading
    def _remove_order_event(self, args: Dict):
        """Apply remove order event to the strategy."""
        market = self._strategy.area.forward_markets[AvailableMarketTypes(args["market_type"])]
        start_time = str_to_pendulum_datetime(args["start_time"])
        end_time = str_to_pendulum_datetime(args["end_time"])
        for slot in market.market_time_slots:
            if not start_time <= slot <= end_time:
                continue
            updater = self._strategy._order_updaters[market].get(slot)
            if updater:
                self._strategy.remove_open_orders(market, slot)
                self._strategy._order_updaters[market].pop(slot)
