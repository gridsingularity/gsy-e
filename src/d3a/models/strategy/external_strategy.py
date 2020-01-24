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

from d3a.models.strategy import BaseStrategy
from d3a_interface.constants_limits import ConstSettings
import json
from d3a.models.market.market_redis_connection import TwoSidedMarketRedisEventSubscriber


class RedisMarketExternalConnection(TwoSidedMarketRedisEventSubscriber):
    def __init__(self, area):
        self.area = area
        super().__init__(None)
        self.areas_to_register = []

    def shutdown(self):
        self.redis_db.terminate_connection()

    def publish_market_cycle(self):
        self.publish(f"{self.area.parent.slug}/{self.area.slug}/market_cycle",
                     self.market.info)

    @property
    def market(self):
        return self.area.parent.next_market

    @property
    def _offer_channel(self):
        return f"{self.area.parent.slug}/{self.area.slug}/offer"

    @property
    def _delete_offer_channel(self):
        return f"{self.area.parent.slug}/{self.area.slug}/delete_offer"

    @property
    def _accept_offer_channel(self):
        return f"{self.area.parent.slug}/{self.area.slug}/accept_offer"

    @property
    def _list_offers_channel(self):
        return f"{self.area.parent.slug}/{self.area.slug}/offers"

    @property
    def _bid_channel(self):
        return f"{self.area.parent.slug}/{self.area.slug}/bid"

    @property
    def _delete_bid_channel(self):
        return f"{self.area.parent.slug}/{self.area.slug}/delete_bid"

    @property
    def _list_bids_channel(self):
        return f"{self.area.parent.slug}/{self.area.slug}/bids"

    @property
    def _offer_response_channel(self):
        return f"{self._offer_channel}/response"

    @property
    def _delete_offer_response_channel(self):
        return f"{self._delete_offer_channel}/response"

    @property
    def _accept_offer_response_channel(self):
        return f"{self._accept_offer_channel}/response"

    @property
    def _list_offers_response_channel(self):
        return f"{self._list_offers_channel}/response"

    @property
    def _bid_response_channel(self):
        return f"{self._bid_channel}/response"

    @property
    def _delete_bid_response_channel(self):
        return f"{self._delete_bid_channel}/response"

    @property
    def _list_bids_response_channel(self):
        return f"{self._list_bids_channel}/response"

    def sub_to_external_requests(self):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            self.redis_db.sub_to_multiple_channels({
                self._offer_channel: self._offer,
                self._delete_offer_channel: self._delete_offer,
                self._accept_offer_channel: self._accept_offer,
                self._list_offers_channel: self._offer_lists,
            })
        else:
            self.redis_db.sub_to_multiple_channels({
                self._offer_channel: self._offer,
                self._delete_offer_channel: self._delete_offer,
                self._bid_channel: self._bid,
                self._delete_bid_channel: self._delete_bid,
                self._list_bids_channel: self._list_bids,
                self._list_offers_channel: self._offer_lists
            })

    @classmethod
    def sanitize_parameters(cls, data_dict):
        return data_dict

    @staticmethod
    def _serialize_offer_list(offer_list):
        return json.dumps([offer.to_JSON_string() for offer in offer_list])

    @staticmethod
    def _serialize_offer_dict(offer_dict):
        return json.dumps({k: v.to_JSON_string() for k, v in offer_dict.items()})

    def _offer_lists(self, payload):
        try:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                                   for _, v in self.market.get_offers().items()]
                self.publish(self._list_offers_response_channel,
                             {"status": "ready", "offer_list": filtered_offers})
            else:
                filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                                   for _, v in self.market.offers.items()
                                   if v.seller == self.area.name]
                self.publish(self._list_offers_response_channel,
                             {"status": "ready", "offer_list": filtered_offers})
        except Exception as e:
            self.publish(self._list_offers_response_channel,
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e)})

    def _accept_offer(self, payload):
        try:
            arguments = self._parse_payload(payload)
            assert set(arguments.keys()) in [{'offer'}, {'offer', 'energy'}]
            arguments['offer_or_id'] = arguments.pop('offer')
            arguments['buyer'] = self.area.name
        except Exception:
            self.publish(
                self._offer_response_channel,
                {"error": "Incorrect accept_offer request. Available parameters: (offer, energy)."}
            )
        else:
            return self._accept_offer_impl(arguments)

    def _offer(self, payload):
        try:
            arguments = self._parse_payload(payload)
            assert set(arguments.keys()) == {'price', 'energy'}
            arguments['seller'] = self.area.name
            arguments['seller_origin'] = self.area.name
        except Exception as e:
            self.publish(
                self._offer_response_channel,
                {"error": "Incorrect offer request. Available parameters: (price, energy)."}
            )
        else:
            return self._offer_impl(arguments)

    def _delete_offer(self, payload):
        try:
            arguments = self._parse_payload(payload)
            assert set(arguments.keys()) == {'offer'}
            arguments['offer_or_id'] = arguments.pop('offer')
        except Exception:
            self.publish(
                self._offer_response_channel,
                {"error": "Incorrect delete offer request. Available parameters: (offer)."}
            )
        else:
            return self._delete_offer_impl(arguments)

    def _bid(self, payload):
        try:
            arguments = self._parse_payload(payload)
            assert set(arguments.keys()) == {'price', 'energy'}
            arguments['buyer'] = self.area.name
            arguments['seller'] = self.area.parent.name
            arguments['buyer_origin'] = self.area.name
        except Exception:
            self.publish(
                self._bid_response_channel,
                {"error": "Incorrect bid request. Available parameters: (price, energy)."}
            )
        else:
            return self._bid_impl(arguments)

    def _delete_bid(self, payload):
        try:
            arguments = self._parse_payload(payload)
            assert set(arguments.keys()) == {'bid'}
            arguments['bid_or_id'] = arguments.pop('bid')
        except Exception:
            self.publish(
                self._delete_bid_response_channel,
                {"error": "Incorrect delete bid request. Available parameters: (bid)."}
            )
        else:
            return self._delete_bid_impl(arguments)

    def _list_bids(self, payload):
        try:
            filtered_bids = [{"id": v.id, "price": v.price, "energy": v.energy}
                             for _, v in self.market.get_bids().items()
                             if v.buyer == self.area.name]
            self.publish(self._list_bids_response_channel,
                         {"status": "ready", "bid_list": filtered_bids})
        except Exception as e:
            self.publish(self._list_bids_response_channel,
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e)})


class ExternalStrategy(BaseStrategy):
    def __init__(self, area):
        super().__init__()
        self.redis = RedisMarketExternalConnection(area)

    def shutdown(self):
        self.redis.shutdown()

    def event_market_cycle(self):
        super().event_market_cycle()
        self.redis.publish_market_cycle()
