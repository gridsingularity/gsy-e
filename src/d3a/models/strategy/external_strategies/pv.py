import json
import logging
from d3a.models.strategy.external_strategies import IncomingRequest
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy, PVPredefinedStrategy
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator
from d3a.models.strategy.external_strategies import register_area, unregister_area, \
    check_for_connected_and_reply


class PVExternalMixin:
    """
    Mixin for enabling an external api for the PV strategies.
    Should always be inherited together with a superclass of PVStrategy.
    """
    def __init__(self, *args, **kwargs):
        self.connected = False
        super().__init__(*args, **kwargs)
        self.redis = ResettableCommunicator()
        self.pending_requests = []

    def event_activate(self):
        super().event_activate()
        self.redis.sub_to_multiple_channels({
            f'{self.device.name}/register_participant': self._register,
            f'{self.device.name}/unregister_participant': self._unregister,
            f'{self.device.name}/offer': self._offer,
            f'{self.device.name}/delete_offer': self._delete_offer,
            f'{self.device.name}/offers': self._list_offers,
        })

    def _register(self, payload):
        self.connected = register_area(self.redis, self.device.name, self.connected)

    def _unregister(self, payload):
        self.connected = unregister_area(self.redis, self.device.name, self.connected)

    def _list_offers(self, payload):
        list_offers_response_channel = f'{self.device.name}/offers/response'
        if not check_for_connected_and_reply(self.redis, list_offers_response_channel,
                                             self.connected):
            return
        try:
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in self.market.get_offers().items()
                               if v.seller == self.device.name]
            self.redis.publish_json(
                list_offers_response_channel,
                {"status": "ready", "offer_list": filtered_offers})
        except Exception as e:
            logging.error(f"Error when handling list offers on area {self.device.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                list_offers_response_channel,
                {"status": "error",
                 "error_message": f"Error when listing offers on area {self.device.name}."})

    def _delete_offer(self, payload):
        delete_offer_response_channel = f'{self.device.name}/delete_offer/response'
        if not check_for_connected_and_reply(self.redis, delete_offer_response_channel,
                                             self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            assert set(arguments.keys()) == {'offer'}
        except Exception as e:
            logging.error(f"Error when handling delete offer request. Payload {payload}. "
                          f"Exception {str(e)}.")
            self.redis.publish_json(
                delete_offer_response_channel,
                {"error": "Incorrect delete offer request. Available parameters: (offer)."}
            )
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, delete_offer_response_channel))

    def _delete_offer_impl(self, arguments, response_channel):
        try:
            self.market.delete_offer(arguments["offer"])
            self.offers.remove_by_id(arguments["offer"])
            self.redis.publish_json(response_channel,
                                    {"status": "ready", "deleted_offer": arguments["offer"]})
        except Exception as e:
            logging.error(f"Error when handling offer delete on area {self.device.name}: "
                          f"Exception: {str(e)}, Offer Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"status": "error",
                 "error_message": f"Error when handling offer delete "
                                  f"on area {self.device.name} with arguments {arguments}."})

    def _offer(self, payload):
        offer_response_channel = f'{self.device.name}/offer/response'
        if not check_for_connected_and_reply(self.redis, offer_response_channel,
                                             self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            assert set(arguments.keys()) == {'price', 'energy'}
            arguments['seller'] = self.device.name
            arguments['seller_origin'] = self.device.name
        except Exception as e:
            logging.error(f"Incorrect offer request. Payload {payload}. Exception {str(e)}.")
            self.redis.publish_json(
                offer_response_channel,
                {"error": "Incorrect offer request. Available parameters: (price, energy)."}
            )
        else:
            self.pending_requests.append(
                IncomingRequest("offer", arguments, offer_response_channel))

    def _offer_impl(self, arguments, response_channel):
        try:
            offer = self.market.offer(**arguments)
            self.offers.post(offer, self.market.id)
            self.redis.publish_json(response_channel,
                                    {"status": "ready", "offer": offer.to_JSON_string()})
        except Exception as e:
            logging.error(f"Error when handling offer create on area {self.device.name}: "
                          f"Exception: {str(e)}, Offer Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"status": "error",
                 "error_message": f"Error when handling offer create "
                                  f"on area {self.device.name} with arguments {arguments}."})

    @property
    def market(self):
        return self.market_area.next_market

    @property
    def market_area(self):
        return self.area

    @property
    def device(self):
        return self.owner

    def event_market_cycle(self):
        super().event_market_cycle()
        market_event_channel = f"{self.device.name}/market_event"
        current_market_info = self.market.info
        current_market_info['available_energy_kWh'] = \
            self.state.available_energy_kWh[self.market.time_slot]
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

    def _area_reconfigure_prices(self, validate=True, **kwargs):
        if not self.connected:
            super()._area_reconfigure_prices(validate, **kwargs)

    def event_tick(self):
        if not self.connected:
            super().event_tick()
        else:
            while len(self.pending_requests) > 0:
                req = self.pending_requests.pop()
                if req.request_type == "offer":
                    self._offer_impl(req.arguments, req.response_channel)
                elif req.request_type == "delete_offer":
                    self._delete_offer_impl(req.arguments, req.response_channel)
                else:
                    assert False, f"Incorrect incoming request name: {req}"

    def event_offer(self, *, market_id, offer):
        if not self.connected:
            super().event_offer(market_id=market_id, offer=offer)

    def event_market_cycle_price(self):
        if not self.connected:
            super().event_market_cycle_price()


class PVExternalStrategy(PVExternalMixin, PVStrategy):
    pass


class PVUserProfileExternalStrategy(PVExternalMixin, PVUserProfileStrategy):
    pass


class PVPredefinedExternalStrategy(PVExternalMixin, PVPredefinedStrategy):
    pass
