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
import json
import logging
from collections import deque
from typing import Dict, List, Union

from d3a_interface.constants_limits import ConstSettings
from pendulum import duration

from d3a.gsy_core.util import get_market_maker_rate_from_config
from d3a.models.strategy.external_strategies import (
    ExternalMixin, IncomingRequest, check_for_connected_and_reply, default_market_info)
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy


class LoadExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the load strategies.
    Should always be inherited together with a superclass of LoadHoursStrategy.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def channel_dict(self):
        return {**super().channel_dict,
                f"{self.channel_prefix}/bid": self.bid,
                f"{self.channel_prefix}/delete_bid": self.delete_bid,
                f"{self.channel_prefix}/list_bids": self.list_bids,
                }

    def filtered_market_bids(self, market) -> List[Dict]:
        """
        Get a representation of each of the asset's bids from the market.
        Args:
            market: Market object that will read the bids from

        Returns: List of bids for the strategy asset

        """

        return [
            {"id": bid.id, "price": bid.price, "energy": bid.energy}
            for _, bid in market.get_bids().items()
            if bid.buyer == self.device.name]

    def event_activate(self, **kwargs):
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels(self.channel_dict)

    def list_bids(self, payload):
        self._get_transaction_id(payload)
        list_bids_response_channel = f"{self.channel_prefix}/response/list_bids"
        if not check_for_connected_and_reply(self.redis, list_bids_response_channel,
                                             self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, list_bids_response_channel))

    def _list_bids_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            self.redis.publish_json(
                response_channel, {
                    "command": "list_bids", "status": "ready",
                    "bid_list": self.filtered_market_bids(market),
                    "transaction_id": arguments.get("transaction_id")})
        except Exception:
            error_message = f"Error when handling list bids on area {self.device.name}"
            logging.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {"command": "list_bids", "status": "error",
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id")})

    def delete_bid(self, payload):
        transaction_id = self._get_transaction_id(payload)
        delete_bid_response_channel = f"{self.channel_prefix}/response/delete_bid"
        if not check_for_connected_and_reply(self.redis,
                                             delete_bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if ("bid" in arguments and arguments["bid"] is not None) and \
                    not self.is_bid_posted(market, arguments["bid"]):
                raise Exception("Bid_id is not associated with any posted bid.")
        except Exception as e:
            self.redis.publish_json(
                delete_bid_response_channel,
                {"command": "bid_delete",
                 "error": f"Incorrect delete bid request. Available parameters: (bid)."
                          f"Exception: {str(e)}",
                 "transaction_id": transaction_id}
            )
        else:
            self.pending_requests.append(
                IncomingRequest("delete_bid", arguments, delete_bid_response_channel))

    def _delete_bid_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments["bid"] if "bid" in arguments else None
            deleted_bids = \
                self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            error_message = (f"Error when handling bid delete on area {self.device.name}: "
                             f"Bid Arguments: {arguments}, "
                             "Bid does not exist on the current market.")
            logging.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "error",
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id")})

    def bid(self, payload):
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        bid_response_channel = f"{self.channel_prefix}/response/bid"
        if not check_for_connected_and_reply(self.redis, bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

        except Exception:
            self.redis.publish_json(
                bid_response_channel,
                {"command": "bid",
                 "error": (
                     "Incorrect bid request. ",
                     f"Required parameters: {required_args}"
                     f"Available parameters: {allowed_args}."),
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("bid", arguments, bid_response_channel))

    def _bid_impl(self, arguments, bid_response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            replace_existing = arguments.get("replace_existing", True)
            assert self.can_bid_be_posted(
                arguments["energy"],
                arguments["price"],
                self.state.get_energy_requirement_Wh(market.time_slot) / 1000.0,
                market,
                replace_existing=replace_existing)

            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                attributes=arguments.get("attributes"),
                requirements=arguments.get("requirements"))
            self.redis.publish_json(
                bid_response_channel, {
                    "command": "bid", "status": "ready",
                    "bid": bid.to_json_string(replace_existing=replace_existing),
                    "transaction_id": arguments.get("transaction_id")})
        except Exception:
            error_message = (f"Error when handling bid create on area {self.device.name}: "
                             f"Bid Arguments: {arguments}")
            logging.exception(error_message)
            self.redis.publish_json(
                bid_response_channel,
                {"command": "bid", "status": "error",
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id")})

    @property
    def _device_info_dict(self):
        return {
            "energy_requirement_kWh":
                self.state.get_energy_requirement_Wh(self.spot_market.time_slot) / 1000.0,
            "energy_active_in_bids": self.posted_bid_energy(self.spot_market.id),
            "energy_traded": self.energy_traded(self.spot_market.id),
            "total_cost": self.energy_traded_costs(self.spot_market.id),
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self.register_on_market_cycle()
        if not self.should_use_default_strategy:
            self.add_entry_in_hrs_per_day()
            self._calculate_active_markets()
            self._update_energy_requirement_future_markets()
            if not self.is_aggregator_controlled:
                market_event_channel = f"{self.channel_prefix}/events/market"
                market_info = self.spot_market.info
                if self.is_aggregator_controlled:
                    market_info.update(default_market_info)
                market_info["device_info"] = self._device_info_dict
                market_info["event"] = "market"
                market_info["area_uuid"] = self.device.uuid
                market_info["device_bill"] = self.device.stats.aggregated_stats["bills"] \
                    if "bills" in self.device.stats.aggregated_stats else None
                market_info["last_market_maker_rate"] = \
                    get_market_maker_rate_from_config(self.area.current_market)
                market_info["last_market_stats"] = \
                    self.market_area.stats.get_price_stats_current_market()
                self.redis.publish_json(market_event_channel, market_info)

            self._delete_past_state()
        else:
            super().event_market_cycle()

    def _area_reconfigure_prices(self, **kwargs):
        if self.should_use_default_strategy:
            super()._area_reconfigure_prices(**kwargs)

    def _incoming_commands_callback_selection(self, req):
        if req.request_type == "bid":
            self._bid_impl(req.arguments, req.response_channel)
        elif req.request_type == "delete_bid":
            self._delete_bid_impl(req.arguments, req.response_channel)
        elif req.request_type == "list_bids":
            self._list_bids_impl(req.arguments, req.response_channel)
        elif req.request_type == "device_info":
            self._device_info_impl(req.arguments, req.response_channel)
        else:
            assert False, f"Incorrect incoming request name: {req}"

    def event_tick(self):
        """Post bids on market tick. This method is triggered by the TICK event."""
        if self.should_use_default_strategy:
            super().event_tick()
        else:
            while self.pending_requests:
                # We want to process requests as First-In-First-Out, so we use popleft
                req = self.pending_requests.popleft()
                self._incoming_commands_callback_selection(req)
            self._dispatch_event_tick_to_external_agent()

    def event_offer(self, *, market_id, offer):
        if self.should_use_default_strategy:
            super().event_offer(market_id=market_id, offer=offer)

    def _bid_aggregator(self, arguments):
        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        try:
            market = self._get_market_from_command_argument(arguments)
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

            replace_existing = arguments.pop("replace_existing", True)
            assert self.can_bid_be_posted(
                arguments["energy"],
                arguments["price"],
                self.state.get_energy_requirement_Wh(market.time_slot) / 1000.0,
                market,
                replace_existing=replace_existing)

            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                attributes=arguments.get("attributes"),
                requirements=arguments.get("requirements")
            )
            return {
                "command": "bid", "status": "ready",
                "bid": bid.to_json_string(replace_existing=replace_existing),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception(f"Error when handling bid on area {self.device.name}")
            return {
                "command": "bid", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling bid create "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}

    def _delete_bid_aggregator(self, arguments):
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments["bid"] if "bid" in arguments else None
            deleted_bids = \
                self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            return {
                "command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception(f"Error when handling delete bid on area {self.device.name}")
            return {
                "command": "bid_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling bid delete "
                                 f"on area {self.device.name} with arguments {arguments}. "
                                 f"Bid does not exist on the current market.",
                "transaction_id": arguments.get("transaction_id")}

    def _list_bids_aggregator(self, arguments):
        try:
            market = self._get_market_from_command_argument(arguments)
            return {
                "command": "list_bids", "status": "ready",
                "bid_list": self.filtered_market_bids(market),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception(f"Error when handling list bids on area {self.device.name}")
            return {
                "command": "list_bids", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing bids on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id")}


class LoadHoursExternalStrategy(LoadExternalMixin, LoadHoursStrategy):
    pass


class LoadProfileExternalStrategy(LoadExternalMixin, DefinedLoadStrategy):
    pass


class LoadForecastExternalStrategy(LoadProfileExternalStrategy):
    """
        Strategy responsible for reading forecast and measurement consumption data via hardware API
    """
    parameters = ("energy_forecast_Wh", "fit_to_limit", "energy_rate_increase_per_update",
                  "update_interval", "initial_buying_rate", "final_buying_rate",
                  "balancing_energy_ratio", "use_market_maker_rate")

    def __init__(self, fit_to_limit=True, energy_rate_increase_per_update=None,
                 update_interval=None,
                 initial_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
                 final_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
                 balancing_energy_ratio: tuple =
                 (ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
                  ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO),
                 use_market_maker_rate: bool = False):
        """
        Constructor of LoadForecastStrategy
        """
        if update_interval is None:
            update_interval = \
                duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        super().__init__(daily_load_profile=None,
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate)

        # Buffers for energy forecast and measurement values,
        # that have been sent by the d3a-api-client in the duration of one market slot
        self.energy_forecast_buffer = {}  # Dict[DateTime, float]
        self.energy_measurement_buffer = {}  # Dict[DateTime, float]

    @property
    def channel_dict(self):
        """Extend channel_dict property with forecast related channels."""
        return {**super().channel_dict,
                f"{self.channel_prefix}/set_energy_forecast": self.set_energy_forecast,
                f"{self.channel_prefix}/set_energy_measurement": self.set_energy_measurement}

    def event_tick(self):
        """Set the energy forecast using pending requests. Extends super implementation.

        This method is triggered by the TICK event.
        """
        # Need to repeat he pending request parsing in order to handle power forecasts
        # from the MQTT subscriber (non-connected admin)
        for req in self.pending_requests:
            if req.request_type == "set_energy_forecast":
                self.set_energy_forecast_impl(req.arguments, req.response_channel)
            elif req.request_type == "set_energy_measurement":
                self.set_energy_measurement_impl(req.arguments, req.response_channel)

        self.pending_requests = deque(
            req for req in self.pending_requests
            if req.request_type not in ["set_energy_forecast", "set_energy_measurement"])

        super().event_tick()

    def _incoming_commands_callback_selection(self, req):
        """Map commands to callbacks for forecast and measurement reading."""
        if req.request_type == "set_energy_forecast":
            self.set_energy_forecast_impl(req.arguments, req.response_channel)
        elif req.request_type == "set_energy_measurement":
            self.set_energy_measurement_impl(req.arguments, req.response_channel)
        else:
            super()._incoming_commands_callback_selection(req)

    def event_market_cycle(self):
        """Update forecast and measurement in state by reading from buffers."""
        self.update_energy_forecast()
        self.update_energy_measurement()
        self._clear_energy_buffers()
        super().event_market_cycle()

    def event_activate_energy(self):
        """This strategy does not need to initiate energy values as they are sent via the API."""
        self._clear_energy_buffers()

    def _clear_energy_buffers(self):
        """Clear forecast and measurement buffers."""
        self.energy_forecast_buffer = {}
        self.energy_measurement_buffer = {}

    def update_energy_forecast(self) -> None:
        """Set energy forecast for future markets."""
        for slot_time, energy_kWh in self.energy_forecast_buffer.items():
            if slot_time >= self.area.spot_market.time_slot:
                self.state.set_desired_energy(energy_kWh * 1000, slot_time, overwrite=True)
                self.state.update_total_demanded_energy(slot_time)

    def update_energy_measurement(self) -> None:
        """Set energy measurement for past markets."""
        for slot_time, energy_kWh in self.energy_measurement_buffer.items():
            if slot_time < self.area.spot_market.time_slot:
                self.state.set_energy_measurement_kWh(energy_kWh, slot_time)

    def _update_energy_requirement_future_markets(self):
        """
        Setting demanded energy for the next slot is already done by update_energy_forecast
        """

    def _read_or_rotate_profiles(self, reconfigure=False):
        pass
