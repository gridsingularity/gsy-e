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
from d3a.models.market.market_structures import Bid


def test_offer_id_stringified():
    market = object()
    bid = Bid(object(), 10, 20, 'A', 'B', market)

    assert isinstance(bid.id, str)
    assert "<object object at" in bid.id


def test_offer_market():
    market = object()
    bid = Bid('a', 10, 20, 'A', 'B', market)

    assert bid.market == market
