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
import datetime
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Tuple, Union  # noqa

from d3a.events import MarketEvent
from d3a_interface.utils import datetime_to_string_incl_seconds, key_in_dict_and_not_none
from pendulum import DateTime, parse


def parse_event_and_parameters_from_json_string(payload) -> Tuple:
    data = json.loads(payload["data"])
    kwargs = data["kwargs"]
    for key in ["offer", "existing_offer", "new_offer"]:
        if key in kwargs:
            kwargs[key] = offer_or_bid_from_json_string(kwargs[key])
    if "trade" in kwargs:
        kwargs["trade"] = trade_from_json_string(kwargs["trade"])
    for key in ["bid", "existing_bid", "new_bid"]:
        if key in kwargs:
            kwargs[key] = offer_or_bid_from_json_string(kwargs[key])
    if "bid_trade" in kwargs:
        kwargs["bid_trade"] = trade_from_json_string(kwargs["bid_trade"])
    event_type = MarketEvent(data["event_type"])
    return event_type, kwargs
