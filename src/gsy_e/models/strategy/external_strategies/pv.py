"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from typing import TYPE_CHECKING, Callable, Dict

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Offer
from gsy_framework.utils import str_to_pendulum_datetime
from pendulum import duration

from gsy_e.gsy_e_core.exceptions import GSyException
from gsy_e.models.strategy.external_strategies import (
    CommandTypeNotSupported,
    ExternalMixin,
    ExternalStrategyConnectionManager,
    IncomingRequest,
    OrderCanNotBePosted,
)
from gsy_e.models.strategy.external_strategies.forecast_mixin import ForecastExternalMixin
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from gsy_e.models.strategy.pv import PVStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy.state import PVState
    from gsy_e.models.strategy import Offers


logger = logging.getLogger(__name__)


class PVExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the PV strategies.
    Should always be inherited together with a superclass of PVStrategy.
    """

    state: "PVState"
    offers: "Offers"
    can_offer_be_posted: Callable
    post_offer: Callable
    set_produced_energy_forecast_in_state: Callable
    _delete_past_state: Callable

    @property
    def channel_dict(self) -> Dict:
        """Offer-related Redis API channels."""
        return {
            **super().channel_dict,
            self.channel_names.offer: self.offer,
            self.channel_names.delete_offer: self.delete_offer,
            self.channel_names.list_offers: self.list_offers,
        }

    def event_activate(self, **kwargs) -> None:
        """Activate the device."""
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels(self.channel_dict)

    def list_offers(self, payload: Dict) -> None:
        """Callback for list offers Redis endpoint."""
        self._get_transaction_id(payload)
        response_channel = self.channel_names.list_offers_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
            self.redis, response_channel, self.connected
        ):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(IncomingRequest("list_offers", arguments, response_channel))

    def _list_offers_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the list_offers callback, publish this device offers."""
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [
                {"id": v.id, "price": v.price, "energy": v.energy}
                for _, v in market.get_offers().items()
                if v.seller.name == self.device.name
            ]
            response = {
                "command": "list_offers",
                "status": "ready",
                "offer_list": filtered_offers,
                "transaction_id": arguments.get("transaction_id"),
            }
        except GSyException:
            error_message = f"Error when handling list offers on area {self.device.name}"
            logger.exception(error_message)
            response = {
                "command": "list_offers",
                "status": "error",
                "error_message": error_message,
                "transaction_id": arguments.get("transaction_id"),
            }
        self.redis.publish_json(response_channel, response)

    def delete_offer(self, payload: Dict) -> None:
        """Callback for delete offer Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        response_channel = self.channel_names.delete_offer_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
            self.redis, response_channel, self.connected
        ):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if arguments.get("offer") and not self.offers.is_offer_posted(
                market.id, arguments["offer"]
            ):
                raise GSyException("Offer_id is not associated with any posted offer.")
        except (GSyException, json.JSONDecodeError):
            logger.exception("Error when handling delete offer request. Payload %s", payload)
            self.redis.publish_json(
                response_channel,
                {
                    "command": "offer_delete",
                    "error": "Incorrect delete offer request. Available parameters: (offer).",
                    "transaction_id": transaction_id,
                },
            )
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, response_channel)
            )

    def _delete_offer_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the delete_offer callback, delete the received offer from market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id
            )
            response = {
                "command": "offer_delete",
                "status": "ready",
                "deleted_offers": deleted_offers,
                "transaction_id": arguments.get("transaction_id"),
            }
        except GSyException:
            error_message = (
                f"Error when handling offer delete on area {self.device.name}: "
                f"Offer Arguments: {arguments}"
            )
            logger.exception(error_message)
            response = {
                "command": "offer_delete",
                "status": "error",
                "error_message": error_message,
                "transaction_id": arguments.get("transaction_id"),
            }
        self.redis.publish_json(response_channel, response)

    def offer(self, payload: Dict) -> None:
        """Callback for offer Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing", "time_slot"})

        response_channel = self.channel_names.offer_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
            self.redis, response_channel, self.connected
        ):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

        except (json.JSONDecodeError, AssertionError):
            logger.exception("Incorrect offer request. Payload %s.", payload)
            self.redis.publish_json(
                response_channel,
                {
                    "command": "offer",
                    "error": (
                        "Incorrect bid request. ",
                        f"Required parameters: {required_args}"
                        f"Available parameters: {allowed_args}.",
                    ),
                    "transaction_id": transaction_id,
                },
            )
        else:
            self.pending_requests.append(IncomingRequest("offer", arguments, response_channel))

    def _offer_impl(self, arguments: Dict, response_channel: str) -> None:
        try:
            replace_existing = arguments.pop("replace_existing", True)
            market = self._get_market_from_command_argument(arguments)
            assert self.can_offer_be_posted(
                arguments["energy"],
                arguments["price"],
                self.state.get_available_energy_kWh(market.time_slot),
                market,
                replace_existing=replace_existing,
            )

            offer_arguments = {
                k: v for k, v in arguments.items() if k not in ["transaction_id", "time_slot"]
            }
            offer = self.post_offer(market, replace_existing=replace_existing, **offer_arguments)

            self.redis.publish_json(
                response_channel,
                {
                    "command": "offer",
                    "status": "ready",
                    "market_type": market.type_name,
                    "offer": offer.to_json_string(),
                    "transaction_id": arguments.get("transaction_id"),
                },
            )
        except (AssertionError, GSyException):
            error_message = (
                f"Error when handling offer create on area {self.device.name}: "
                f"Offer Arguments: {arguments}"
            )
            logger.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {
                    "command": "offer",
                    "status": "error",
                    "market_type": market.type_name,
                    "error_message": error_message,
                    "transaction_id": arguments.get("transaction_id"),
                },
            )

    @property
    def _device_info_dict(self):
        return {
            **super()._device_info_dict,
            "available_energy_kWh": self.state.get_available_energy_kWh(
                self.spot_market.time_slot
            ),
            "energy_active_in_offers": self.offers.open_offer_energy(self.spot_market.id),
            "energy_traded": self.energy_traded(self.spot_market.id),
            "total_cost": self.energy_traded_costs(self.spot_market.id),
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self._update_connection_status()
        if not self.should_use_default_strategy:
            self.set_produced_energy_forecast_in_state(reconfigure=False)
            self._set_energy_measurement_of_last_market()
            if not self.is_aggregator_controlled:
                self.populate_market_info_to_connected_user()
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
            market.id, arguments["offer"]
        ):
            raise GSyException("Offer_id is not associated with any posted offer.")

        try:
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id
            )
            response = {
                "command": "offer_delete",
                "status": "ready",
                "area_uuid": self.device.uuid,
                "deleted_offers": deleted_offers,
                "transaction_id": arguments.get("transaction_id"),
            }
        except GSyException:
            response = {
                "command": "offer_delete",
                "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling offer delete "
                f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id"),
            }
        return response

    def _list_offers_aggregator(self, arguments: Dict) -> Dict:
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [
                {"id": v.id, "price": v.price, "energy": v.energy}
                for v in market.get_offers().values()
                if v.seller.name == self.device.name
            ]
            response = {
                "command": "list_offers",
                "status": "ready",
                "offer_list": filtered_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id"),
            }
        except GSyException:
            response = {
                "command": "list_offers",
                "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing offers on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id"),
            }
        return response

    def _bid_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the bid endpoint when sent by aggregator."""
        try:
            market = self._get_market_from_command_argument(arguments)
            if self.area.is_market_settlement(market.id):
                if not self.state.can_post_settlement_bid(market.time_slot):
                    raise OrderCanNotBePosted(
                        "The PV did not produce too little energy, "
                        "settlement bid can not be posted."
                    )
                response = self._bid_aggregator_impl(
                    arguments,
                    market,
                    self._get_time_slot_from_external_arguments(arguments),
                    self.state.get_unsettled_deviation_kWh(market.time_slot),
                )
            else:
                raise CommandTypeNotSupported("Bid not supported for PV on spot markets.")

        except (OrderCanNotBePosted, CommandTypeNotSupported) as ex:
            response = {
                "command": "offer",
                "status": "error",
                "area_uuid": self.device.uuid,
                "market_type": market.type_name,
                "error_message": "Error when handling offer create "
                f"on area {self.device.name} with arguments {arguments}:"
                f"{ex}",
                "transaction_id": arguments.get("transaction_id"),
            }

        return response

    def _offer_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the offer endpoint when sent by aggregator."""
        try:
            market = self._get_market_from_command_argument(arguments)
            if self.area.is_market_settlement(market.id):
                if not self.state.can_post_settlement_offer(market.time_slot):
                    raise OrderCanNotBePosted(
                        "The PV did not produce too much energy, "
                        "settlement offer can not be posted."
                    )
                available_energy_kWh = self.state.get_unsettled_deviation_kWh(market.time_slot)
            elif self.area.is_market_future(market.id):
                available_energy_kWh = self.state.get_available_energy_kWh(
                    str_to_pendulum_datetime(arguments["time_slot"])
                )
            elif self.area.is_market_spot(market.id):
                available_energy_kWh = self.state.get_available_energy_kWh(market.time_slot)
            else:
                logger.debug(
                    "The order cannot be posted on the market (arguments: %s, market_id: %s)",
                    arguments,
                    market.id,
                )
                raise OrderCanNotBePosted("The order cannot be posted on the market.")

            response = self._offer_aggregator_impl(
                arguments,
                market,
                self._get_time_slot_from_external_arguments(arguments),
                available_energy_kWh,
            )

        except OrderCanNotBePosted as ex:
            response = {
                "command": "offer",
                "status": "error",
                "market_type": market.type_name,
                "area_uuid": self.device.uuid,
                "error_message": "Error when handling offer create "
                f"on area {self.device.name} with arguments {arguments}:"
                f"{ex}",
                "transaction_id": arguments.get("transaction_id"),
            }

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

    # pylint: disable=too-many-arguments,unused-argument
    def __init__(
        self,
        panel_count=1,
        initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
        final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
        fit_to_limit: bool = True,
        update_interval=duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
        energy_rate_decrease_per_update=None,
        use_market_maker_rate: bool = False,
        cloud_coverage: int = None,
        capacity_kW: float = None,
        **kwargs,
    ):
        """
        Constructor of PVForecastStrategy
        """
        if kwargs.get("linear_pricing") is not None:
            fit_to_limit = kwargs.get("linear_pricing")

        super().__init__(
            panel_count=panel_count,
            initial_selling_rate=initial_selling_rate,
            final_selling_rate=final_selling_rate,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval,
            energy_rate_decrease_per_update=energy_rate_decrease_per_update,
            use_market_maker_rate=use_market_maker_rate,
        )

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

    def set_produced_energy_forecast_in_state(self, reconfigure=False) -> None:
        """
        Setting produced energy for the next slot is already done by update_energy_forecast
        """

    def _set_energy_measurement_of_last_market(self):
        """
        Setting energy measurement for the previous slot is already done by
        update_energy_measurement
        """
