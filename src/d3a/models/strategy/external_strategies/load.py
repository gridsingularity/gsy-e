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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_requests = []

    def event_activate(self):
        super().event_activate()
        self.redis.sub_to_multiple_channels({
            f'{self.device.name}/register_participant': self._register,
            f'{self.device.name}/unregister_participant': self._unregister,
            f'{self.device.name}/bid': self._bid,
            f'{self.device.name}/delete_bid': self._delete_bid,
            f'{self.device.name}/bids': self._list_bids,
            f'{self.device.name}/stats': self._area_stats
        })

    def _list_bids(self, payload):
        list_bids_response_channel = f'{self.device.name}/bids/response'
        if not check_for_connected_and_reply(self.redis, list_bids_response_channel,
                                             self.connected):
            return
        try:
            filtered_bids = [{"id": v.id, "price": v.price, "energy": v.energy}
                             for _, v in self.market.get_bids().items()
                             if v.buyer == self.device.name]
            self.redis.publish_json(
                list_bids_response_channel,
                {"status": "ready", "bid_list": filtered_bids})
        except Exception as e:
            logging.error(f"Error when handling list bids on area {self.device.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                list_bids_response_channel,
                {"status": "error",
                 "error_message": f"Error when listing bids on area {self.device.name}."})

    def _delete_bid(self, payload):
        delete_bid_response_channel = f'{self.device.name}/delete_bid/response'
        if not check_for_connected_and_reply(self.redis,
                                             delete_bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            assert set(arguments.keys()) == {'bid'}
        except Exception:
            self.redis.publish_json(
                delete_bid_response_channel,
                {"error": "Incorrect delete bid request. Available parameters: (bid)."}
            )
        else:
            self.pending_requests.append(
                IncomingRequest("delete_bid", arguments, delete_bid_response_channel))

    def _delete_bid_impl(self, arguments, response_channel):
        try:
            self.remove_bid_from_pending(arguments["bid"], self.market.id)
            self.redis.publish_json(response_channel,
                                    {"status": "ready", "bid_deleted": arguments["bid"]})
        except Exception as e:
            logging.error(f"Error when handling bid delete on area {self.device.name}: "
                          f"Exception: {str(e)}, Bid Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"status": "error",
                 "error_message": f"Error when handling bid delete "
                                  f"on area {self.device.name} with arguments {arguments}."})

    def _bid(self, payload):
        bid_response_channel = f'{self.device.name}/bid/response'
        if not check_for_connected_and_reply(self.redis, bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            assert set(arguments.keys()) == {'price', 'energy'}
            arguments['buyer_origin'] = self.device.name
            print(f"arguments: {arguments}")
        except Exception:
            self.redis.publish_json(
                bid_response_channel,
                {"error": "Incorrect bid request. Available parameters: (price, energy)."}
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
            self.redis.publish_json(bid_response_channel,
                                    {"status": "ready", "bid": bid.to_JSON_string()})
            print(f"bid : {bid}")
        except Exception as e:
            logging.error(f"Error when handling bid create on area {self.device.name}: "
                          f"Exception: {str(e)}, Bid Arguments: {arguments}")
            self.redis.publish_json(
                bid_response_channel,
                {"status": "error",
                 "error_message": f"Error when handling bid create "
                                  f"on area {self.device.name} with arguments {arguments}."})

    def event_market_cycle(self):
        self.register_on_market_cycle()
        super().event_market_cycle()
        if not self.connected:
            return
        market_event_channel = f"{self.device.name}/market_event"
        current_market_info = self.market.info
        current_market_info['energy_requirement_kWh'] = \
            self.energy_requirement_Wh.get(self.market.time_slot, 0.0) / 1000.0
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
