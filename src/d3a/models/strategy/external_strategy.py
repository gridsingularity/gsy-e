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

from redis import StrictRedis
import json
from d3a.d3a_core.redis_communication import REDIS_URL
from d3a.models.market.market_structures import trade_bid_info_from_JSON_string


class RedisExternalConnection:
    def __init__(self, area):
        self.area = area
        self.redis_db = StrictRedis.from_url(REDIS_URL)
        self.pubsub = self.redis_db.pubsub()
        self.areas_to_register = []
        self.sub_to_external_requests()

    def publish(self, channel, data):
        self.redis_db.publish(channel, json.dumps(data))

    def sub_to_external_requests(self):
        offer_channel = f"{self.area.parent.slug}/{self.area.slug}/offer"
        delete_offer_channel = f"{self.area.parent.slug}/{self.area.slug}/delete_offer"
        accept_offer_channel = f"{self.area.parent.slug}/{self.area.slug}/accept_offer"
        list_offers_channel = f"{self.area.parent.slug}/{self.area.slug}/offers"

        self.pubsub.subscribe(**{
            offer_channel: self._offer,
            delete_offer_channel: self._delete_offer,
            accept_offer_channel: self._accept_offer,
            list_offers_channel: self._offer_lists
        })
        self.pubsub.run_in_thread(daemon=True)

    @staticmethod
    def _parse_payload(payload):
        data_dict = json.loads(payload["data"])
        if isinstance(data_dict, (str, bytes)):
            data_dict = json.loads(data_dict)
        if "trade_bid_info" in data_dict and data_dict["trade_bid_info"] is not None:
            data_dict["trade_bid_info"] = \
                trade_bid_info_from_JSON_string(data_dict["trade_bid_info"])
        # if "offer_or_id" in data_dict and data_dict["offer_or_id"] is not None:
        #     if isinstance(data_dict["offer_or_id"], str):
        #         data_dict["offer_or_id"] = offer_from_JSON_string(data_dict["offer_or_id"])
        # if "offer" in data_dict and data_dict["offer"] is not None:
        #     if isinstance(data_dict["offer_or_id"], str):
        #         data_dict["offer_or_id"] = offer_from_JSON_string(data_dict["offer_or_id"])

        return data_dict

    @staticmethod
    def _serialize_offer_list(offer_list):
        return json.dumps([offer.to_JSON_string() for offer in offer_list])

    @staticmethod
    def _serialize_offer_dict(offer_dict):
        return json.dumps({k: v.to_JSON_string() for k, v in offer_dict.items()})

    def _offer_lists(self, payload):
        try:
            return_data = self._serialize_offer_dict(self.area.next_market.offers)
            print(return_data)
            self.publish(f"{self.area.parent.slug}/{self.area.slug}/offers/response",
                         {"status": "ready", "offer_list": return_data})
        except Exception as e:
            self.publish(f"{self.area.parent.slug}/{self.area.slug}/offers/response",
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e)})

    def _accept_offer(self, payload):
        try:
            trade = self.area.next_market.accept_offer(**self._parse_payload(payload))
            self.publish(f"{self.area.parent.slug}/{self.area.slug}/accept_offer/response",
                         {"status": "ready", "trade": trade.to_JSON_string()})
        except Exception as e:
            self.publish(f"{self.area.parent.slug}/{self.area.slug}/accept_offer/response",
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e)})

    def _offer(self, payload):
        try:
            offer = self.area.next_market.offer(**self._parse_payload(payload))
            self.publish(f"{self.area.parent.slug}/{self.area.slug}/offer/response",
                         {"status": "ready", "offer": offer.to_JSON_string()})
        except Exception as e:
            self.publish(f"{self.area.parent.slug}/{self.area.slug}/offer/response",
                         {"status": "error",  "exception": str(type(e)),
                          "error_message": str(e)})

    def _delete_offer(self, payload):
        try:
            self.area.next_market.delete_offer(**self._parse_payload(payload))
            self.publish(f"{self.area.parent.slug}/{self.area.slug}/delete_offer/response",
                         {"status": "ready"})
        except Exception as e:
            self.publish(f"{self.area.parent.slug}/{self.area.slug}/delete_offer/response",
                         {"status": "error", "exception": str(type(e)),
                          "error_message": str(e)})


class ExternalStrategy(BaseStrategy):
    def __init__(self, area):
        super().__init__()
        self.redis = RedisExternalConnection(area)

    def event_market_cycle(self):
        pass
