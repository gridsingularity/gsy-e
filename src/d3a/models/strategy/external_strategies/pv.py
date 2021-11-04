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
from typing import Dict, Callable, TYPE_CHECKING

from d3a_interface.constants_limits import ConstSettings
from d3a_interface.data_classes import Offer
from pendulum import duration

from d3a.d3a_core.util import get_market_maker_rate_from_config
from d3a.models.strategy.external_strategies import (
    ExternalMixin, IncomingRequest, ExternalStrategyConnectionManager, default_market_info)
from d3a.models.strategy.external_strategies.forecast_mixin import ForecastExternalMixin
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a.models.strategy.pv import PVStrategy

if TYPE_CHECKING:
    from d3a.models.state import PVState
    from d3a.models.strategy import Offers


class PVExternalMixin(ExternalMixin):

    state: "PVState"
    offers: "Offers"
    can_offer_be_posted: Callable
    post_offer: Callable
    set_produced_energy_forecast_kWh_future_markets: Callable
    _delete_past_state: Callable

    """
    Mixin for enabling an external api for the PV strategies.
    Should always be inherited together with a superclass of PVStrategy.
    """
    @property
    def channel_dict(self) -> Dict:
        """Offer-related Redis API channels."""
        return {**super().channel_dict,
                f"{self.channel_prefix}/offer": self.offer,
                f"{self.channel_prefix}/delete_offer": self.delete_offer,
                f"{self.channel_prefix}/list_offers": self.list_offers,
                }

    def event_activate(self, **kwargs) -> None:
        """Activate the device."""
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels(self.channel_dict)

    def list_offers(self, payload: Dict) -> None:
        """Callback for list offers Redis endpoint."""
        self._get_transaction_id(payload)
        list_offers_response_channel = f"{self.channel_prefix}/response/list_offers"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, list_offers_response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_offers", arguments, list_offers_response_channel))

    def _list_offers_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the list_offers callback, publish this device offers."""
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in market.get_offers().items()
                               if v.seller == self.device.name]
            response = {"command": "list_offers", "status": "ready",
                        "offer_list": filtered_offers,
                        "transaction_id": arguments.get("transaction_id")}
        except Exception:
            error_message = f"Error when handling list offers on area {self.device.name}"
            logging.exception(error_message)
            response = {"command": "list_offers", "status": "error",
                        "error_message": error_message,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

    def delete_offer(self, payload: Dict) -> None:
        """Callback for delete offer Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        delete_offer_response_channel = f"{self.channel_prefix}/response/delete_offer"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, delete_offer_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if arguments.get("offer") and not self.offers.is_offer_posted(
                    market.id, arguments["offer"]):
                raise Exception("Offer_id is not associated with any posted offer.")
        except Exception:
            logging.exception("Error when handling delete offer request. Payload %s", payload)
            self.redis.publish_json(
                delete_offer_response_channel,
                {"command": "offer_delete",
                 "error": "Incorrect delete offer request. Available parameters: (offer).",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, delete_offer_response_channel))

    def _delete_offer_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the delete_offer callback, delete the received offer from market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            response = {"command": "offer_delete", "status": "ready",
                        "deleted_offers": deleted_offers,
                        "transaction_id": arguments.get("transaction_id")}
        except Exception:
            error_message = (f"Error when handling offer delete on area {self.device.name}: "
                             f"Offer Arguments: {arguments}")
            logging.exception(error_message)
            response = {"command": "offer_delete", "status": "error",
                        "error_message": error_message,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

    def offer(self, payload: Dict) -> None:
        """Callback for offer Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        offer_response_channel = f"{self.channel_prefix}/response/offer"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, offer_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

        except Exception:
            logging.exception("Incorrect offer request. Payload %s.", payload)
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

    def _offer_impl(self, arguments: Dict, response_channel: str) -> None:
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
            **super()._device_info_dict,
            "available_energy_kWh":
                self.state.get_available_energy_kWh(self.spot_market.time_slot),
            "energy_active_in_offers": self.offers.open_offer_energy(self.spot_market.id),
            "energy_traded": self.energy_traded(self.spot_market.id),
            "total_cost": self.energy_traded_costs(self.spot_market.id),
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self._update_connection_status()
        if not self.should_use_default_strategy:
            self.set_produced_energy_forecast_kWh_future_markets(reconfigure=False)
            self._set_energy_measurement_of_last_market()
            if not self.is_aggregator_controlled:
                market_event_channel = f"{self.channel_prefix}/events/market"
                market_info = self.spot_market.info
                if self.is_aggregator_controlled:
                    market_info.update(default_market_info)
                market_info["device_info"] = self._device_info_dict
                market_info["event"] = "market"
                market_info["device_bill"] = self.device.stats.aggregated_stats.get("bills")
                market_info["area_uuid"] = self.device.uuid
                market_info["last_market_maker_rate"] = (
                    get_market_maker_rate_from_config(self.area.current_market))
                market_info["last_market_stats"] = (
                    self.area.stats.get_price_stats_current_market())
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

    def event_tick(self) -> None:
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

    def event_offer(self, *, market_id: str, offer: Offer) -> None:
        """This method is triggered by the OFFER event."""
        if self.should_use_default_strategy:
            super().event_offer(market_id=market_id, offer=offer)

    def _delete_offer_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the delete offer endpoint when sent by aggregator."""
        market = self._get_market_from_command_argument(arguments)
        if arguments.get("offer") and not self.offers.is_offer_posted(
                market.id, arguments["offer"]):
            raise Exception("Offer_id is not associated with any posted offer.")

        try:
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            response = {
                "command": "offer_delete", "status": "ready",
                "area_uuid": self.device.uuid,
                "deleted_offers": deleted_offers,
                "transaction_id": arguments.get("transaction_id")
            }
        except Exception:
            response = {
                "command": "offer_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling offer delete "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _list_offers_aggregator(self, arguments: Dict) -> Dict:
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for v in market.get_offers().values()
                               if v.seller == self.device.name]
            response = {
                "command": "list_offers", "status": "ready", "offer_list": filtered_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            response = {
                "command": "list_offers", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing offers on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _offer_aggregator(self, arguments: Dict) -> Dict:
        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})
        try:
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

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

            response = {
                "command": "offer",
                "status": "ready",
                "offer": offer.to_json_string(replace_existing=replace_existing),
                "transaction_id": arguments.get("transaction_id"),
                "area_uuid": self.device.uuid
            }
        except Exception:
            logging.exception("Failed to post PV offer.")
            response = {
                "command": "offer", "status": "error",
                "error_message": "Error when handling offer create "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        return response


class PVExternalStrategy(PVExternalMixin, PVStrategy):
    """Strategy class for external PV devices."""


class PVUserProfileExternalStrategy(PVExternalMixin, PVUserProfileStrategy):
    """Strategy class for external PV devices that support profile reading."""


class PVPredefinedExternalStrategy(PVExternalMixin, PVPredefinedStrategy):
    """Strategy class for external PV devices with predefined profile."""


class PVForecastExternalStrategy(ForecastExternalMixin, PVPredefinedExternalStrategy):
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

    def set_produced_energy_forecast_kWh_future_markets(self, reconfigure=False) -> None:
        """
        Setting produced energy for the next slot is already done by produced_energy_forecast_kWh
        """

    def _read_or_rotate_profiles(self, reconfigure=False) -> None:
        """Overridden with empty implementation to disable reading profile from DB."""

    def _set_energy_measurement_of_last_market(self):
        pass
