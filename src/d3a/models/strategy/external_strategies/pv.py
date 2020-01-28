import json
import logging
from d3a.models.strategy.pv import PVStrategy
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator


class PVExternalStrategy(PVStrategy):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = ResettableCommunicator()

    def event_activate(self):
        super().event_activate()
        self.redis.sub_to_multiple_channels({
            f'{self.area.name}/offer': self._offer,
            f'{self.area.name}/offers': self._list_offers
        })

    def _list_offers(self, payload):
        list_offers_response_channel = f'{self.area.name}/offers/response'
        try:
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in self.owner.current_market.get_offers().items()
                               if v.buyer == self.area.name]
            self.redis.publish(
                list_offers_response_channel,
                {"status": "ready", "offer_list": filtered_offers})
        except Exception as e:
            logging.error(f"Error when handling list offers on area {self.area.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                list_offers_response_channel,
                {"status": "error",
                 "error_message": f"Error when listing offers on area {self.area.name}."})

    def _offer(self, payload):
        offer_response_channel = f'{self.area.name}/offer/response'
        try:
            arguments = json.loads(payload)
            assert set(arguments.keys()) == {'price', 'energy'}
            arguments['seller'] = self.area.name
            arguments['seller_origin'] = self.area.name
        except Exception:
            self.redis.publish_json(
                offer_response_channel,
                {"error": "Incorrect offer request. Available parameters: (price, energy)."}
            )
        else:
            try:
                offer = self.owner.current_market.offer(**arguments)
                self.redis.publish_json(offer_response_channel,
                                        {"status": "ready", "offer": offer.to_JSON_string()})
            except Exception as e:
                logging.error(f"Error when handling offer create on area {self.area.name}: "
                              f"Exception: {str(e)}, Offer Arguments: {arguments}")
                self.redis.publish_json(
                    offer_response_channel,
                    {"status": "error",
                     "error_message": f"Error when handling offer create "
                                      f"on area {self.area.name} with arguments {arguments}."})

    def event_market_cycle(self):
        super().event_market_cycle()
        market_event_channel = f"{self.area.name}/market_event"
        current_market_info = self.owner.current_market.info
        current_market_info['available_energy_kWh'] = \
            self.state.available_energy_kWh[self.owner.current_market.time_slot]
        self.redis.publish_json(market_event_channel, current_market_info)

    def _init_price_update(self, fit_to_limit, energy_rate_increase_per_update, update_interval,
                           use_market_maker_rate, initial_buying_rate, final_buying_rate):
        pass

    def event_activate_price(self):
        pass

    def _area_reconfigure_prices(self, validate=True, **kwargs):
        pass

    def event_tick(self):
        pass

    def event_offer(self, *, market_id, offer):
        pass

    def event_market_cycle_price(self):
        pass
