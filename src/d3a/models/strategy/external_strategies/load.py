import json
import logging
from d3a.models.strategy.external_strategies import IncomingRequest
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.external_strategies import ExternalMixin, check_for_connected_and_reply


class LoadExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the load strategies.
    Should always be inherited together with a superclass of LoadHoursStrategy.
    """
    def __init__(self, external_redis_communicator, *args, **kwargs):
        print(f"LOAD: {external_redis_communicator}")
        super().__init__(external_redis_communicator, *args, **kwargs)
        print(f"DICT: |{self.__dict__}")

    def event_activate(self):
        super().event_activate()
        print(f"load_channel_prefix: {self.channel_prefix}")
        list_sub = self.redis.sub_to_multiple_channels({
            f'{self.channel_prefix}/register_participant': self._register,
            f'{self.channel_prefix}/unregister_participant': self._unregister,
            f'{self.channel_prefix}/bid': self._bid,
            f'{self.channel_prefix}/delete_bid': self._delete_bid,
            f'{self.channel_prefix}/list_bids': self._list_bids,
            f'{self.channel_prefix}/device_info': self._device_info,
        })
        print(f"list_sub: {list_sub}")

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
                             for _, v in self.market.get_bids().items()
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
                    not self.is_bid_posted(self.market, arguments["bid"]):
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
            deleted_bids = self.remove_bid_from_pending(self.market.id, bid_id=to_delete_bid_id)
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
            pending_bid_energy = sum(
                req.arguments["energy"]
                for req in self.pending_requests
                if req.request_type == "bid"
            )
            if not self.can_bid_be_posted(
                    arguments["energy"] + pending_bid_energy,
                    self.energy_requirement_Wh.get(self.market.time_slot, 0.0) / 1000.0,
                    self.market):
                self.redis.publish_json(
                    bid_response_channel,
                    {"command": "bid",
                     "error": "Bid cannot be posted. Required energy has been reached with "
                              "existing bids.",
                     "transaction_id": transaction_id})
                return
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
            bid = self.post_bid(
                self.market,
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
                self.energy_requirement_Wh.get(self.market.time_slot, 0.0) / 1000.0
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self.register_on_market_cycle()
        super().event_market_cycle()
        if not self.connected:
            return
        self._reset_event_tick_counter()
        market_event_channel = f"{self.channel_prefix}/events/market"
        current_market_info = self.market.info
        current_market_info['device_info'] = self._device_info_dict
        current_market_info["event"] = "market"
        current_market_info['device_bill'] = self.device.stats.aggregated_stats["bills"]
        current_market_info['last_market_stats'] = \
            self.market_area.stats.get_price_stats_current_market()
        self.redis.publish_json(market_event_channel, current_market_info)

    def _init_price_update(self, fit_to_limit, energy_rate_increase_per_update, update_interval,
                           use_market_maker_rate, initial_buying_rate, final_buying_rate):
        if not self.connected:
            super()._init_price_update(
                fit_to_limit, energy_rate_increase_per_update, update_interval,
                use_market_maker_rate, initial_buying_rate, final_buying_rate)

    def event_activate_price(self):
        if not self.connected:
            super().event_activate_price()

    def _area_reconfigure_prices(self, final_buying_rate):
        if not self.connected:
            super()._area_reconfigure_prices(final_buying_rate)

    def event_tick(self):
        if not self.connected:
            super().event_tick()
        else:
            while len(self.pending_requests) > 0:
                req = self.pending_requests.pop()
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
            self._dispatch_event_tick_to_external_agent()

    def event_offer(self, *, market_id, offer):
        if not self.connected:
            super().event_offer(market_id=market_id, offer=offer)

    def event_market_cycle_prices(self):
        if not self.connected:
            super().event_market_cycle_prices()


class LoadHoursExternalStrategy(LoadExternalMixin, LoadHoursStrategy):
    pass


class LoadProfileExternalStrategy(LoadExternalMixin, DefinedLoadStrategy):
    pass
