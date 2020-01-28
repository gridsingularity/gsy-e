import json
import logging
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.d3a_core.redis_connections.redis_area_market_communicator import ResettableCommunicator


class LoadHoursExternalStrategy(LoadHoursStrategy):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = ResettableCommunicator()

    def event_activate(self):
        super().event_activate()
        self.redis.sub_to_multiple_channels({
            f'{self.area.name}/bid': self._bid,
            f'{self.area.name}/bids': self._list_bids
        })

    def _list_bids(self, payload):
        list_bids_response_channel = f'{self.area.name}/bids/response'
        try:
            filtered_bids = [{"id": v.id, "price": v.price, "energy": v.energy}
                             for _, v in self.owner.current_market.get_bids().items()
                             if v.buyer == self.area.name]
            self.redis.publish(
                list_bids_response_channel,
                {"status": "ready", "bid_list": filtered_bids})
        except Exception as e:
            logging.error(f"Error when handling list bids on area {self.area.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                list_bids_response_channel,
                {"status": "error",
                 "error_message": f"Error when listing bids on area {self.area.name}."})

    def _bid(self, payload):
        bid_response_channel = f'{self.area.name}/bid/response'
        try:
            arguments = json.loads(payload)
            assert set(arguments.keys()) == {'price', 'energy'}
            arguments['buyer'] = self.area.name
            arguments['seller'] = self.area.parent.name
            arguments['buyer_origin'] = self.area.name
        except Exception:
            self.redis.publish_json(
                bid_response_channel,
                {"error": "Incorrect bid request. Available parameters: (price, energy)."}
            )
        else:
            try:
                bid = self.owner.current_market.bid(**arguments)
                self.redis.publish_json(bid_response_channel,
                                        {"status": "ready", "bid": bid.to_JSON_string()})
            except Exception as e:
                logging.error(f"Error when handling bid create on area {self.area.name}: "
                              f"Exception: {str(e)}, Bid Arguments: {arguments}")
                self.redis.publish_json(
                    bid_response_channel,
                    {"status": "error",
                     "error_message": f"Error when handling bid create "
                                      f"on area {self.area.name} with arguments {arguments}."})

    def event_market_cycle(self):
        super().event_market_cycle()
        market_event_channel = f"{self.area.name}/market_event"
        self.redis.publish_json(market_event_channel, self.owner.current_market)

    def _init_price_update(self, fit_to_limit, energy_rate_increase_per_update, update_interval,
                           use_market_maker_rate, initial_buying_rate, final_buying_rate):
        pass

    def event_activate_price(self):
        pass

    def _area_reconfigure_prices(self, final_buying_rate):
        pass

    def event_tick(self):
        pass

    def event_offer(self, *, market_id, offer):
        pass

    def event_market_cycle_prices(self):
        pass
