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
import traceback
from d3a.models.strategy.external_strategies import IncomingRequest
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy, LoadForecastStrategy
from d3a.models.strategy.external_strategies import ExternalMixin, check_for_connected_and_reply
from d3a.d3a_core.redis_connections.aggregator_connection import default_market_info
from d3a.d3a_core.util import get_current_market_maker_rate


class LoadExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the load strategies.
    Should always be inherited together with a superclass of LoadHoursStrategy.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def _channel_dict(self):
        return {
            f'{self.channel_prefix}/register_participant': self._register,
            f'{self.channel_prefix}/unregister_participant': self._unregister,
            f'{self.channel_prefix}/bid': self._bid,
            f'{self.channel_prefix}/delete_bid': self._delete_bid,
            f'{self.channel_prefix}/list_bids': self._list_bids,
            f'{self.channel_prefix}/device_info': self._device_info,
            }

    @property
    def channel_dict(self):
        return self._channel_dict

    def event_activate(self):
        super().event_activate()
        self.redis.sub_to_multiple_channels(self.channel_dict)

    def _list_bids(self, payload):
        self._get_transaction_id(payload)
        list_bids_response_channel = f'{self.channel_prefix}/response/list_bids'
        if not check_for_connected_and_reply(self.redis, list_bids_response_channel,
                                             self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, list_bids_response_channel))

    def _list_bids_impl(self, arguments, response_channel):
        try:
            filtered_bids = [{"id": v.id, "price": v.price, "energy": v.energy}
                             for _, v in self.next_market.get_bids().items()
                             if v.buyer == self.device.name]
            self.redis.publish_json(
                response_channel,
                {"command": "list_bids", "status": "ready", "bid_list": filtered_bids,
                 "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling list bids on area {self.device.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                response_channel,
                {"command": "list_bids", "status": "error",
                 "error_message": f"Error when listing bids on area {self.device.name}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    def _delete_bid(self, payload):
        transaction_id = self._get_transaction_id(payload)
        delete_bid_response_channel = f'{self.channel_prefix}/response/delete_bid'
        if not check_for_connected_and_reply(self.redis,
                                             delete_bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            if ("bid" in arguments and arguments["bid"] is not None) and \
                    not self.is_bid_posted(self.next_market, arguments["bid"]):
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
            to_delete_bid_id = arguments["bid"] if "bid" in arguments else None
            deleted_bids = \
                self.remove_bid_from_pending(self.next_market.id, bid_id=to_delete_bid_id)
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                 "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling bid delete on area {self.device.name}: "
                          f"Exception: {str(e)}, Bid Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "error",
                 "error_message": f"Error when handling bid delete "
                                  f"on area {self.device.name} with arguments {arguments}. "
                                  f"Bid does not exist on the current market.",
                 "transaction_id": arguments.get("transaction_id", None)})

    def _bid(self, payload):
        transaction_id = self._get_transaction_id(payload)
        bid_response_channel = f'{self.channel_prefix}/response/bid'
        if not check_for_connected_and_reply(self.redis, bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            assert set(arguments.keys()) == {'price', 'energy', 'transaction_id'}
            arguments['buyer_origin'] = self.device.name
        except Exception:
            self.redis.publish_json(
                bid_response_channel,
                {"command": "bid",
                 "error": "Incorrect bid request. Available parameters: (price, energy).",
                 "transaction_id": transaction_id}
            )
        else:
            self.pending_requests.append(
                IncomingRequest("bid", arguments, bid_response_channel))

    def _bid_impl(self, arguments, bid_response_channel):
        try:
            assert self.can_bid_be_posted(
                arguments["energy"],
                arguments["price"],
                self.energy_requirement_Wh.get(self.next_market.time_slot, 0.0) / 1000.0,
                self.next_market)

            bid = self.post_bid(
                self.next_market,
                arguments["price"],
                arguments["energy"],
                buyer_origin=arguments["buyer_origin"]
            )
            self.redis.publish_json(
                bid_response_channel,
                {"command": "bid", "status": "ready", "bid": bid.to_JSON_string(),
                 "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling bid create on area {self.device.name}: "
                          f"Exception: {str(e)}, Bid Arguments: {arguments}")
            self.redis.publish_json(
                bid_response_channel,
                {"command": "bid", "status": "error",
                 "error_message": f"Error when handling bid create "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    @property
    def _device_info_dict(self):
        return {
            'energy_requirement_kWh':
                self.energy_requirement_Wh.get(self.next_market.time_slot, 0.0) / 1000.0
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self.register_on_market_cycle()
        if not self.should_use_default_strategy:
            super().update_state()
            self._reset_event_tick_counter()
            market_event_channel = f"{self.channel_prefix}/events/market"
            market_info = self.next_market.info
            if self.is_aggregator_controlled:
                market_info.update(default_market_info)
            market_info['device_info'] = self._device_info_dict
            market_info["event"] = "market"
            market_info["area_uuid"] = self.device.uuid
            market_info['device_bill'] = self.device.stats.aggregated_stats["bills"] \
                if "bills" in self.device.stats.aggregated_stats else None
            market_info["last_market_maker_rate"] = \
                get_current_market_maker_rate(self.area.current_market.time_slot) \
                if self.area.current_market else None
            if self.connected:
                market_info['last_market_stats'] = \
                    self.market_area.stats.get_price_stats_current_market()
                self.redis.publish_json(market_event_channel, market_info)
            if self.is_aggregator_controlled:
                self.redis.aggregator.add_batch_market_event(self.device.uuid,
                                                             market_info,
                                                             self.area.global_objects)
        else:
            super().event_market_cycle()

    def _init_price_update(self, fit_to_limit, energy_rate_increase_per_update, update_interval,
                           use_market_maker_rate, initial_buying_rate, final_buying_rate):
        if not self.connected:
            super()._init_price_update(
                fit_to_limit, energy_rate_increase_per_update, update_interval,
                use_market_maker_rate, initial_buying_rate, final_buying_rate)

    def event_activate_price(self):
        if not self.connected:
            super().event_activate_price()

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
        if not self.connected and not self.is_aggregator_controlled:
            super().event_tick()
        else:
            while len(self.pending_requests) > 0:
                req = self.pending_requests.pop()
                self._incoming_commands_callback_selection(req)
        self._dispatch_event_tick_to_external_agent()

    def event_offer(self, *, market_id, offer):
        if self.should_use_default_strategy:
            super().event_offer(market_id=market_id, offer=offer)

    def event_market_cycle_prices(self):
        if self.should_use_default_strategy:
            super().event_market_cycle_prices()

    def _update_bid_aggregator(self, arguments):
        assert set(arguments.keys()) == {'price', 'energy', 'type', 'transaction_id'}
        bid_rate = arguments["price"] / arguments["energy"]
        if bid_rate < 0.0:
            return {
                "command": "update_bid", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": "Updated bid needs to have a positive price.",
                "transaction_id": arguments.get("transaction_id", None)}
        with self.lock:
            existing_bids = list(self.get_posted_bids(self.next_market))
            existing_bid_energy = sum([bid.energy for bid in existing_bids])
            for bid in existing_bids:
                assert bid.buyer == self.owner.name
                if bid.id in self.next_market.bids.keys():
                    bid = self.next_market.bids[bid.id]
                self.next_market.delete_bid(bid.id)

                self.remove_bid_from_pending(self.next_market.id, bid.id)
            if len(existing_bids) > 0:
                updated_bid = self.post_bid(self.next_market, bid_rate * existing_bid_energy,
                                            existing_bid_energy, buyer_origin=self.device.name)
                return {
                    "command": "update_bid", "status": "ready",
                    "bid": updated_bid.to_JSON_string(),
                    "area_uuid": self.device.uuid,
                    "transaction_id": arguments.get("transaction_id", None)}
            else:
                return {
                    "command": "update_bid", "status": "error",
                    "area_uuid": self.device.uuid,
                    "error_message": "Updated bid would only work if the old exist in market.",
                    "transaction_id": arguments.get("transaction_id", None)}

    def _bid_aggregator(self, arguments):
        try:
            assert set(arguments.keys()) == {'price', 'energy', 'type', 'transaction_id'}
            arguments['buyer_origin'] = self.device.name

            assert self.can_bid_be_posted(
                arguments["energy"],
                arguments["price"],
                self.energy_requirement_Wh.get(self.next_market.time_slot, 0.0) / 1000.0,
                self.next_market)

            bid = self.post_bid(
                self.next_market,
                arguments["price"],
                arguments["energy"],
                buyer_origin=arguments["buyer_origin"]
            )
            return {
                "command": "bid", "status": "ready", "bid": bid.to_JSON_string(),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)}
        except Exception as e:
            logging.error(f"Error when handling bid on area {self.device.name}: "
                          f"Exception: {str(e)}. Traceback {traceback.format_exc()}")
            return {
                "command": "bid", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling bid create "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id", None)}

    def _delete_bid_aggregator(self, arguments):
        try:
            to_delete_bid_id = arguments["bid"] if "bid" in arguments else None
            deleted_bids = \
                self.remove_bid_from_pending(self.next_market.id, bid_id=to_delete_bid_id)
            return {
                "command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)}
        except Exception as e:
            logging.error(f"Error when handling delete bid on area {self.device.name}: "
                          f"Exception: {str(e)}")
            return {
                "command": "bid_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling bid delete "
                                 f"on area {self.device.name} with arguments {arguments}. "
                                 f"Bid does not exist on the current market.",
                "transaction_id": arguments.get("transaction_id", None)}

    def _list_bids_aggregator(self, arguments):
        try:
            filtered_bids = [{"id": v.id, "price": v.price, "energy": v.energy}
                             for _, v in self.next_market.get_bids().items()
                             if v.buyer == self.device.name]
            return {
                "command": "list_bids", "status": "ready", "bid_list": filtered_bids,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)}
        except Exception as e:
            logging.error(f"Error when handling list bids on area {self.device.name}: "
                          f"Exception: {str(e)}")
            return {
                "command": "list_bids", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing bids on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id", None)}


class LoadForecastExternalStrategy(LoadExternalMixin, LoadForecastStrategy):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def channel_dict(self):
        return {**self._channel_dict,
                f'{self.channel_prefix}/set_power_forecast': self._set_power_forecast}

    # def _set_power_forecast(self, payload):
    #     transaction_id = self._get_transaction_id(payload)
    #     power_forecast_response_channel = \
    #         f'{self.channel_prefix}/response/set_load_power_forecast'
    #     if not check_for_connected_and_reply(self.redis, power_forecast_response_channel,
    #                                          self.connected):
    #         return
    #     try:
    #         arguments = json.loads(payload["data"])
    #         assert set(arguments.keys()) == {'load_power_forecast', 'transaction_id'}
    #     except Exception as e:
    #         logging.error(
    #             f"Incorrect _set_load_power_forecast request. "
    #             f"Payload {payload}. Exception {str(e)}.")
    #         self.redis.publish_json(
    #             power_forecast_response_channel,
    #             {"command": "set_load_power_forecast",
    #              "error": "Incorrect _set_load_power_forecast request. "
    #                       "Available parameters: (load_power_forecast).",
    #              "transaction_id": transaction_id})
    #     else:
    #         self.pending_requests.append(
    #             IncomingRequest("set_load_power_forecast", arguments,
    #                             power_forecast_response_channel))
    #
    # def _set_power_forecast_impl(self, arguments, response_channel):
    #     try:
    #         assert arguments["load_power_forecast"] >= 0.0
    #         self.power_forecast_buffer_W = arguments["load_power_forecast"]
    #         self.redis.publish_json(
    #             response_channel,
    #             {"command": "set_load_power_forecast", "status": "ready",
    #              "transaction_id": arguments.get("transaction_id", None)})
    #     except Exception as e:
    #         logging.error(f"Error when handling _set_power_forecast_impl "
    #                       f"on area {self.device.name}: "
    #                       f"Exception: {str(e)}, Arguments: {arguments}")
    #         self.redis.publish_json(
    #             response_channel,
    #             {"command": "set_load_power_forecast", "status": "error",
    #              "error_message": f"Error when handling _set_power_forecast_impl "
    #                               f"on area {self.device.name} with arguments {arguments}.",
    #              "transaction_id": arguments.get("transaction_id", None)})

    def _incoming_commands_callback_selection(self, req):
        if req.request_type == "bid":
            self._bid_impl(req.arguments, req.response_channel)
        elif req.request_type == "delete_bid":
            self._delete_bid_impl(req.arguments, req.response_channel)
        elif req.request_type == "list_bids":
            self._list_bids_impl(req.arguments, req.response_channel)
        elif req.request_type == "device_info":
            self._device_info_impl(req.arguments, req.response_channel)
        elif req.request_type == "set_power_forecast":
            self._set_power_forecast_impl(req.arguments, req.response_channel)
        else:
            assert False, f"Incorrect incoming request name: {req}"

    def event_market_cycle(self):
        self.update_energy_forecast()
        super().event_market_cycle()


class LoadHoursExternalStrategy(LoadExternalMixin, LoadHoursStrategy):
    pass


class LoadProfileExternalStrategy(LoadExternalMixin, DefinedLoadStrategy):
    pass
