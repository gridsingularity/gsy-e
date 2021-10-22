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

from d3a_interface.constants_limits import ConstSettings
from pendulum import duration

from d3a.d3a_core.util import get_market_maker_rate_from_config
from d3a.models.strategy.external_strategies import (
    ExternalMixin, IncomingRequest, check_for_connected_and_reply, default_market_info)
from d3a.models.strategy.external_strategies.incoming_order_validator import IncomingOrderValidator
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a.models.strategy.pv import PVStrategy


class PVExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the PV strategies.
    Should always be inherited together with a superclass of PVStrategy.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def channel_dict(self):
        return {**super().channel_dict,
                f"{self.channel_prefix}/offer": self.offer,
                f"{self.channel_prefix}/delete_offer": self.delete_offer,
                f"{self.channel_prefix}/list_offers": self.list_offers,
                }

    def event_activate(self, **kwargs):
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels(self.channel_dict)

    def list_offers(self, payload):
        self._get_transaction_id(payload)
        list_offers_response_channel = f"{self.channel_prefix}/response/list_offers"
        if not check_for_connected_and_reply(self.redis, list_offers_response_channel,
                                             self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_offers", arguments, list_offers_response_channel))

    def _list_offers_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in market.get_offers().items()
                               if v.seller == self.device.name]
            self.redis.publish_json(
                response_channel,
                {"command": "list_offers", "status": "ready", "offer_list": filtered_offers,
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            error_message = f"Error when handling list offers on area {self.device.name}"
            logging.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {"command": "list_offers", "status": "error",
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id", None)})

    def delete_offer(self, payload):
        transaction_id = self._get_transaction_id(payload)
        delete_offer_response_channel = f"{self.channel_prefix}/response/delete_offer"
        if not check_for_connected_and_reply(self.redis, delete_offer_response_channel,
                                             self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if ("offer" in arguments and arguments["offer"] is not None) and \
                    not self.offers.is_offer_posted(market.id, arguments["offer"]):
                raise Exception("Offer_id is not associated with any posted offer.")
        except Exception:
            logging.exception(f"Error when handling delete offer request. Payload {payload}")
            self.redis.publish_json(
                delete_offer_response_channel,
                {"command": "offer_delete",
                 "error": "Incorrect delete offer request. Available parameters: (offer).",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, delete_offer_response_channel))

    def _delete_offer_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments["offer"] if "offer" in arguments else None
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            self.redis.publish_json(
                response_channel,
                {"command": "offer_delete", "status": "ready",
                 "deleted_offers": deleted_offers,
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            error_message = (f"Error when handling offer delete on area {self.device.name}: "
                             f"Offer Arguments: {arguments}")
            logging.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {"command": "offer_delete", "status": "error",
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id")})

    def offer(self, payload):
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        offer_response_channel = f"{self.channel_prefix}/response/offer"
        if not check_for_connected_and_reply(self.redis, offer_response_channel,
                                             self.connected):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

        except Exception:
            logging.exception(f"Incorrect offer request. Payload {payload}.")
            self.redis.publish_json(
                offer_response_channel,
                {"command": "offer",
                 "error": (
                     "Incorrect bid request. ",
                     f"Required parameters: {required_args}"
                     f"Available parameters: {allowed_args}."),
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("offer", arguments, offer_response_channel))

    def _offer_impl(self, arguments, response_channel):
        try:
            replace_existing = arguments.pop("replace_existing", True)
            market = self._get_market_from_command_argument(arguments)
            assert self.can_offer_be_posted(
                arguments["energy"],
                arguments["price"],
                self.state.get_available_energy_kWh(market.time_slot),
                market,
                replace_existing=replace_existing)

            offer_arguments = {
                k: v for k, v in arguments.items() if k not in ["transaction_id", "time_slot"]}
            offer = self.post_offer(
                market, replace_existing=replace_existing, **offer_arguments)

            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "ready",
                 "offer": offer.to_json_string(replace_existing=replace_existing),
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            error_message = (f"Error when handling offer create on area {self.device.name}: "
                             f"Offer Arguments: {arguments}")
            logging.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "error",
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id")})

    @property
    def _device_info_dict(self):
        return {
            "available_energy_kWh":
                self.state.get_available_energy_kWh(self.spot_market.time_slot),
            "energy_active_in_offers": self.offers.open_offer_energy(self.spot_market.id),
            "energy_traded": self.energy_traded(self.spot_market.id),
            "total_cost": self.energy_traded_costs(self.spot_market.id),
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self.register_on_market_cycle()
        if not self.should_use_default_strategy:
            self.set_produced_energy_forecast_kWh_future_markets(reconfigure=False)
            if not self.is_aggregator_controlled:
                market_event_channel = f"{self.channel_prefix}/events/market"
                market_info = self.spot_market.info
                if self.is_aggregator_controlled:
                    market_info.update(default_market_info)
                market_info["device_info"] = self._device_info_dict
                market_info["event"] = "market"
                market_info["device_bill"] = self.device.stats.aggregated_stats["bills"] \
                    if "bills" in self.device.stats.aggregated_stats else None
                market_info["area_uuid"] = self.device.uuid
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
        if req.request_type == "offer":
            self._offer_impl(req.arguments, req.response_channel)
        elif req.request_type == "delete_offer":
            self._delete_offer_impl(req.arguments, req.response_channel)
        elif req.request_type == "list_offers":
            self._list_offers_impl(req.arguments, req.response_channel)
        elif req.request_type == "device_info":
            self._device_info_impl(req.arguments, req.response_channel)
        else:
            assert False, f"Incorrect incoming request name: {req}"

    def event_tick(self):
        """Process aggregator requests on market tick. Extends super implementation.

        This method is triggered by the TICK event.
        """
        if not self.connected and not self.is_aggregator_controlled:
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

    def _delete_offer_aggregator(self, arguments):
        market = self._get_market_from_command_argument(arguments)
        if ("offer" in arguments and arguments["offer"] is not None) and \
                not self.offers.is_offer_posted(market.id, arguments["offer"]):
            raise Exception("Offer_id is not associated with any posted offer.")

        try:
            to_delete_offer_id = arguments["offer"] if "offer" in arguments else None
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            return {
                "command": "offer_delete", "status": "ready",
                "area_uuid": self.device.uuid,
                "deleted_offers": deleted_offers,
                "transaction_id": arguments.get("transaction_id")
            }
        except Exception:
            return {
                "command": "offer_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling offer delete "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}

    def _list_offers_aggregator(self, arguments):
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for v in market.get_offers().values()
                               if v.seller == self.device.name]
            return {
                "command": "list_offers", "status": "ready", "offer_list": filtered_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            return {
                "command": "list_offers", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing offers on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id")}

    def _offer_aggregator(self, arguments):
        response_message = ""
        validator = IncomingOrderValidator(
            accept_degrees_of_freedom=self.simulation_config.enable_degrees_of_freedom)
        validator.validate(arguments)
        if validator.warnings:
            response_message = ". ".join(warning.message for warning in validator.warnings)

        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        # Check that all required arguments have been provided
        assert all(arg in arguments.keys() for arg in required_args)
        # Check that every provided argument is allowed
        assert all(arg in allowed_args for arg in arguments.keys())

        try:
            replace_existing = arguments.pop("replace_existing", True)
            market = self._get_market_from_command_argument(arguments)

            assert self.can_offer_be_posted(
                arguments["energy"],
                arguments["price"],
                self.state.get_available_energy_kWh(market.time_slot),
                market,
                replace_existing=replace_existing)

            offer_arguments = {k: v
                               for k, v in arguments.items()
                               if k not in ["transaction_id", "type", "time_slot"]}

            offer = self.post_offer(
                market, replace_existing=replace_existing, **offer_arguments)

            return {
                "command": "offer",
                "status": "ready",
                "offer": offer.to_json_string(replace_existing=replace_existing),
                "transaction_id": arguments.get("transaction_id"),
                "area_uuid": self.device.uuid,
                "message": response_message}
        except Exception:
            logging.exception("Failed to post PV offer.")
            return {
                "command": "offer", "status": "error",
                "error_message": f"Error when handling offer create "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}


class PVExternalStrategy(PVExternalMixin, PVStrategy):
    pass


class PVUserProfileExternalStrategy(PVExternalMixin, PVUserProfileStrategy):
    pass


class PVPredefinedExternalStrategy(PVExternalMixin, PVPredefinedStrategy):
    pass


class PVForecastExternalStrategy(PVPredefinedExternalStrategy):
    """
        Strategy responsible for reading forecast and measurement production data via hardware API
    """
    parameters = ("energy_forecast_Wh", "panel_count", "initial_selling_rate",
                  "final_selling_rate", "fit_to_limit", "update_interval",
                  "energy_rate_decrease_per_update", "use_market_maker_rate")

    def __init__(
            self, panel_count=1,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
            fit_to_limit: bool = True,
            update_interval=duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
            energy_rate_decrease_per_update=None,
            use_market_maker_rate: bool = False):
        """
        Constructor of PVForecastStrategy
        """
        super().__init__(panel_count=panel_count,
                         initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit,
                         update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
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
        # Need to repeat the pending request parsing in order to handle energy forecasts
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

    def _clear_energy_buffers(self):
        """Clear forecast and measurement buffers."""
        self.energy_forecast_buffer = {}
        self.energy_measurement_buffer = {}

    def event_activate_energy(self):
        """This strategy does not need to initiate energy values as they are sent via the API."""
        self._clear_energy_buffers()

    def update_energy_forecast(self) -> None:
        """Set energy forecast for future markets."""
        for slot_time, energy_kWh in self.energy_forecast_buffer.items():
            if slot_time >= self.area.spot_market.time_slot:
                self.state.set_available_energy(energy_kWh, slot_time, overwrite=True)

    def update_energy_measurement(self) -> None:
        """Set energy measurement for past markets."""
        for slot_time, energy_kWh in self.energy_measurement_buffer.items():
            if slot_time < self.area.spot_market.time_slot:
                self.state.set_energy_measurement_kWh(energy_kWh, slot_time)

    def set_produced_energy_forecast_kWh_future_markets(self, reconfigure=False):
        """
        Setting produced energy for the next slot is already done by produced_energy_forecast_kWh
        """

    def _read_or_rotate_profiles(self, reconfigure=False):
        pass
