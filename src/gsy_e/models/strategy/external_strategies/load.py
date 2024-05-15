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
from typing import TYPE_CHECKING, Callable, Dict, List, Union

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.utils import str_to_pendulum_datetime
from pendulum import duration

from gsy_e.gsy_e_core.exceptions import GSyException
from gsy_e.models.strategy.energy_parameters.load import (
    LoadProfileForecastEnergyParams, LoadHoursForecastEnergyParams)
from gsy_e.models.strategy.external_strategies import (CommandTypeNotSupported, ExternalMixin,
                                                       ExternalStrategyConnectionManager,
                                                       IncomingRequest, OrderCanNotBePosted)
from gsy_e.models.strategy.external_strategies.forecast_mixin import ForecastExternalMixin
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy

if TYPE_CHECKING:
    from gsy_e.models.market.two_sided import TwoSidedMarket
    from gsy_e.models.strategy.state import LoadState

logger = logging.getLogger(__name__)


class LoadExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the load strategies.
    Should always be inherited together with a superclass of LoadHoursStrategy.
    """

    state: "LoadState"
    is_bid_posted: Callable
    can_bid_be_posted: Callable
    remove_bid_from_pending: Callable
    post_bid: Callable
    posted_bid_energy: Callable
    _delete_past_state: Callable
    _cycle_energy_parameters: Callable

    @property
    def channel_dict(self) -> Dict:
        """Bid-related Redis API channels."""
        return {**super().channel_dict,
                self.channel_names.bid: self.bid,
                self.channel_names.delete_bid: self.delete_bid,
                self.channel_names.list_bids: self.list_bids,
                }

    def filtered_market_bids(self, market: "TwoSidedMarket") -> List[Dict]:
        """
        Get a representation of each of the asset's bids from the market.
        Args:
            market: Market object that will read the bids from

        Returns: List of bids for the strategy asset

        """

        return [
            {"id": bid.id, "price": bid.price, "energy": bid.energy}
            for _, bid in market.get_bids().items()
            if bid.buyer.name == self.device.name]

    def event_activate(self, **kwargs):
        """Activate the device."""
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels(self.channel_dict)

    def list_bids(self, payload: Dict) -> None:
        """Callback for list bids Redis endpoint."""
        self._get_transaction_id(payload)
        response_channel = self.channel_names.list_bids_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, response_channel))

    def _list_bids_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the list_bids callback, publish this device bids."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response = {
                    "command": "list_bids", "status": "ready",
                    "bid_list": self.filtered_market_bids(market),
                    "transaction_id": arguments.get("transaction_id")}
        except GSyException:
            error_message = f"Error when handling list bids on area {self.device.name}"
            logger.exception(error_message)
            response = {"command": "list_bids", "status": "error",
                        "error_message": error_message,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

    def delete_bid(self, payload: Dict) -> None:
        """Callback for delete bid Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        response_channel = self.channel_names.delete_bid_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if arguments.get("bid") and not self.is_bid_posted(market, arguments["bid"]):
                raise GSyException("Bid_id is not associated with any posted bid.")
        except (GSyException, json.JSONDecodeError) as exception:
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete",
                 "error": f"Incorrect delete bid request. Available parameters: (bid)."
                          f"Exception: {str(exception)}",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("delete_bid", arguments, response_channel))

    def _delete_bid_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the delete_bid callback, delete the received bid from market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments.get("bid")
            deleted_bids = self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            response = {"command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                        "transaction_id": arguments.get("transaction_id")}
        except GSyException:
            error_message = (f"Error when handling bid delete on area {self.device.name}: "
                             f"Bid Arguments: {arguments}, "
                             "Bid does not exist on the current market.")
            logger.exception(error_message)
            response = {"command": "bid_delete", "status": "error",
                        "error_message": error_message,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

    def bid(self, payload: Dict) -> None:
        """Callback for bid Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        response_channel = self.channel_names.bid_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        if (  # Check that all required arguments have been provided
              all(arg in arguments.keys() for arg in required_args)
              # Check that every provided argument is allowed
              and all(arg in allowed_args for arg in arguments.keys())):
            self.pending_requests.append(
                IncomingRequest("bid", arguments, response_channel))
        else:
            self.redis.publish_json(
                response_channel,
                {"command": "bid",
                 "error": (
                     "Incorrect bid request. ",
                     f"Required parameters: {required_args}"
                     f"Available parameters: {allowed_args}."),
                 "transaction_id": transaction_id})

    def _bid_impl(self, arguments: Dict, bid_response_channel: str) -> None:
        """Implementation for the bid callback, post the bid in the market."""
        try:
            response_message = ""
            arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
            if filtered_fields:
                response_message = (
                    "The following arguments are not supported for this market and have been "
                    f"removed from your order: {filtered_fields}.")

            market = self._get_market_from_command_argument(arguments)
            replace_existing = arguments.get("replace_existing", True)
            assert self.can_bid_be_posted(
                arguments["energy"],
                arguments["price"],
                self.get_energy_requirement_kWh_from_market(market),
                market,
                replace_existing=replace_existing)

            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing)
            response = {
                    "command": "bid", "status": "ready",
                    "bid": bid.to_json_string(),
                    "market_type": market.type_name,
                    "transaction_id": arguments.get("transaction_id"),
                    "message": response_message}
        except (AssertionError, GSyException):
            error_message = (f"Error when handling bid create on area {self.device.name}: "
                             f"Bid Arguments: {arguments}")
            logger.exception(error_message)
            response = {"command": "bid", "status": "error",
                        "error_message": error_message,
                        "market_type": market.type_name,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(bid_response_channel, response)

    @property
    def _device_info_dict(self) -> Dict:
        """Return the asset info."""
        return {
            **super()._device_info_dict,
            "energy_requirement_kWh":
                self.state.get_energy_requirement_Wh(self.spot_market.time_slot) / 1000.0,
            "energy_active_in_bids": self.posted_bid_energy(self.spot_market.id),
            "energy_traded": self.energy_traded(self.spot_market.id),
            "total_cost": self.energy_traded_costs(self.spot_market.id),
        }

    def event_market_cycle(self) -> None:
        """Handler for the market cycle event."""
        self._reject_all_pending_requests()
        self._update_connection_status()
        if not self.should_use_default_strategy:
            self._cycle_energy_parameters()
            if not self.is_aggregator_controlled:
                self.populate_market_info_to_connected_user()
            self._delete_past_state()
        else:
            super().event_market_cycle()

    def _area_reconfigure_prices(self, **kwargs):
        if self.should_use_default_strategy:
            super()._area_reconfigure_prices(**kwargs)

    def _incoming_commands_callback_selection(self, req: IncomingRequest) -> None:
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

    def event_tick(self) -> None:
        """Post bids on market tick. This method is triggered by the TICK event."""
        if self.should_use_default_strategy:
            super().event_tick()
        else:
            while self.pending_requests:
                # We want to process requests as First-In-First-Out, so we use popleft
                req = self.pending_requests.popleft()
                self._incoming_commands_callback_selection(req)
            self._dispatch_event_tick_to_external_agent()

    def event_offer(self, *, market_id, offer) -> None:
        """This method is triggered by the OFFER event."""
        if self.should_use_default_strategy:
            super().event_offer(market_id=market_id, offer=offer)

    def _offer_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the offer endpoint when sent by aggregator."""
        try:
            market = self._get_market_from_command_argument(arguments)
            if self.area.is_market_settlement(market.id):
                if not self.state.can_post_settlement_offer(market.time_slot):
                    raise OrderCanNotBePosted("The load did not consume too much energy, ",
                                              "settlement offer can not be posted")
                response = (
                    self._offer_aggregator_impl(
                        arguments, market, self._get_time_slot_from_external_arguments(arguments),
                        self.state.get_unsettled_deviation_kWh(
                            market.time_slot)))
            else:
                raise CommandTypeNotSupported("Offer not supported for Loads on spot markets.")

        except (OrderCanNotBePosted, CommandTypeNotSupported) as ex:
            response = {
                "command": "offer", "status": "error",
                "market_type": market.type_name,
                "area_uuid": self.device.uuid,
                "error_message": "Error when handling offer create "
                                 f"on area {self.device.name} with arguments {arguments}:"
                                 f"{ex}",
                "transaction_id": arguments.get("transaction_id")}

        return response

    def _bid_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the bid endpoint when sent by aggregator."""
        try:
            market = self._get_market_from_command_argument(arguments)
            if self.area.is_market_settlement(market.id):
                if not self.state.can_post_settlement_bid(market.time_slot):
                    raise OrderCanNotBePosted("The load did not consume to little energy, "
                                              "settlement bid can not be posted.")
                required_energy_kWh = self.state.get_unsettled_deviation_kWh(market.time_slot)
            elif self.area.is_market_future(market.id):
                required_energy_kWh = self.state.get_energy_requirement_Wh(
                    str_to_pendulum_datetime(arguments["time_slot"])) / 1000.
            elif self.area.is_market_spot(market.id):
                required_energy_kWh = (
                        self.state.get_energy_requirement_Wh(market.time_slot) / 1000.)
            else:
                logger.debug("The order cannot be posted on the market. "
                             "(arguments: %s, market_id: %s", arguments, market.id)
                raise OrderCanNotBePosted("The order cannot be posted on the market.")

            response = (
                self._bid_aggregator_impl(arguments, market,
                                          self._get_time_slot_from_external_arguments(arguments),
                                          required_energy_kWh))

        except OrderCanNotBePosted as ex:
            response = {
                "command": "offer", "status": "error",
                "market_type": market.type_name,
                "area_uuid": self.device.uuid,
                "error_message": "Error when handling bid create "
                                 f"on area {self.device.name} with arguments {arguments}:"
                                 f"{ex}",
                "transaction_id": arguments.get("transaction_id")}

        return response

    def _delete_bid_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the delete bid endpoint when sent by aggregator."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments.get("bid")
            deleted_bids = (
                self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id))
            response = {
                "command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except GSyException:
            logger.exception("Error when handling delete bid on area %s", self.device.name)
            response = {
                "command": "bid_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": "Error when handling bid delete "
                                 f"on area {self.device.name} with arguments {arguments}. "
                                 "Bid does not exist on the current market.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _list_bids_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the list bids endpoint when sent by aggregator."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response = {
                "command": "list_bids", "status": "ready",
                "bid_list": self.filtered_market_bids(market),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except GSyException:
            logger.exception("Error when handling list bids on area %s", self.device.name)
            response = {
                "command": "list_bids", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing bids on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id")}
        return response


class LoadHoursExternalStrategy(LoadExternalMixin, LoadHoursStrategy):
    """Concrete LoadHoursStrategy class with external connection capabilities"""


class LoadProfileExternalStrategy(LoadExternalMixin, DefinedLoadStrategy):
    """Concrete DefinedLoadStrategy class with external connection capabilities"""


class LoadForecastExternalStrategyMixin(ForecastExternalMixin):
    """
        Strategy responsible for reading forecast and measurement consumption data via hardware API
    """

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

    def _update_energy_requirement_in_state(self):
        """
        Setting demanded energy for the next slot is already done by update_energy_forecast
        """

    def _set_energy_measurement_of_last_market(self):
        """
        Setting measured energy for the previous slot is already done by update_energy_measurement
        """


class LoadProfileForecastExternalStrategy(
        LoadForecastExternalStrategyMixin, LoadProfileExternalStrategy):
    """
        Strategy responsible for reading forecast and measurement consumption data via hardware
        API. In case the hardware API is not available the normal profile strategy will be used
        instead.
    """
    # pylint: disable=too-many-arguments
    def __init__(self, fit_to_limit=True, energy_rate_increase_per_update=None,
                 update_interval=None,
                 initial_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
                 final_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
                 balancing_energy_ratio: tuple =
                 (ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
                  ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO),
                 use_market_maker_rate: bool = False,
                 daily_load_profile=None,
                 daily_load_profile_uuid=None):
        """
        Constructor of LoadForecastStrategy
        """
        if update_interval is None:
            update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        super().__init__(daily_load_profile=None,
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate,
                         daily_load_profile_uuid=daily_load_profile_uuid,
                         )

        self._energy_params = LoadProfileForecastEnergyParams(
            daily_load_profile, daily_load_profile_uuid)


class LoadHoursForecastExternalStrategy(
        LoadForecastExternalStrategyMixin, LoadHoursExternalStrategy):
    """
        Strategy responsible for reading forecast and measurement consumption data via hardware
        API. In case the hardware API is not available the normal load hours strategy will be used
        instead.
    """
    # pylint: disable=too-many-arguments,unused-argument
    def __init__(self, fit_to_limit=True, energy_rate_increase_per_update=None,
                 update_interval=None,
                 initial_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
                 final_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
                 balancing_energy_ratio: tuple =
                 (ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
                  ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO),
                 use_market_maker_rate: bool = False,
                 avg_power_W=0,
                 hrs_of_day=None):
        """
        Constructor of LoadForecastStrategy
        """
        if update_interval is None:
            update_interval = duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        super().__init__(None,
                         fit_to_limit=fit_to_limit,
                         energy_rate_increase_per_update=energy_rate_increase_per_update,
                         update_interval=update_interval,
                         final_buying_rate=final_buying_rate,
                         initial_buying_rate=initial_buying_rate,
                         balancing_energy_ratio=balancing_energy_ratio,
                         use_market_maker_rate=use_market_maker_rate)

        self._energy_params = LoadHoursForecastEnergyParams(
            avg_power_W, hrs_of_day)
