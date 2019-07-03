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
import pytest

from d3a.models.market.market_structures import Offer, BalancingOffer


@pytest.mark.parametrize("offer", [Offer, BalancingOffer])
def test_offer_id_stringified(offer):
    offer = offer(object(), 10, 20, 'A')

    assert isinstance(offer.id, str)
    assert "<object object at" in offer.id
