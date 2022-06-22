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
from typing import Tuple

from gsy_framework.data_classes import Trade, BaseBidOffer

from gsy_e.events import MarketEvent


def parse_event_and_parameters_from_json_string(payload) -> Tuple:
    data = json.loads(payload["data"])
    kwargs = data["kwargs"]
    for key in ["offer", "existing_offer", "new_offer"]:
        if key in kwargs:
            kwargs[key] = BaseBidOffer.from_json(kwargs[key])
    if "trade" in kwargs:
        kwargs["trade"] = Trade.from_json(kwargs["trade"])
    for key in ["bid", "existing_bid", "new_bid"]:
        if key in kwargs:
            kwargs[key] = BaseBidOffer.from_json(kwargs[key])
    if "bid_trade" in kwargs:
        kwargs["bid_trade"] = Trade.from_json(kwargs["bid_trade"])
    event_type = MarketEvent(data["event_type"])
    return event_type, kwargs
