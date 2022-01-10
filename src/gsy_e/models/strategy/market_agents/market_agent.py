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
from typing import Optional

from gsy_framework.constants_limits import ConstSettings
from numpy.random import random

from gsy_e.constants import TIME_FORMAT
from gsy_e.models.strategy import BaseStrategy, _TradeLookerUpper


class MarketAgent(BaseStrategy):
    """Base class for inter area agents implementations."""
    parameters = ("owner", "higher_market", "lower_market", "min_offer_age")

    def __init__(self, *, owner, higher_market, lower_market,
                 min_offer_age=ConstSettings.MASettings.MIN_OFFER_AGE):
        """
        :param min_offer_age: Minimum age of offer before transferring
        """
        super().__init__()
        self.owner = owner
        self._validate_constructor_arguments(min_offer_age)

        # serialization parameters
        self.higher_market = higher_market
        self.lower_market = lower_market
        self.min_offer_age = min_offer_age

        self._create_engines()
        self.name = owner.name
        self.uuid = owner.uuid

    def _create_engines(self):
        """Base method for creating the engines"""

    @property
    def time_slot_str(self) -> Optional[str]:
        """Return time_slot of the inter area agent. For future markets it is None."""
        return (self.higher_market.time_slot.format(TIME_FORMAT)
                if self.higher_market.time_slot else None)

    @staticmethod
    def _validate_constructor_arguments(min_offer_age):
        assert 0 <= min_offer_age <= 360

    def area_reconfigure_event(self, *args, **kwargs):
        """Reconfigure the minimum offer age at runtime with the given value."""
        if "min_offer_age" in kwargs:
            min_offer_age = kwargs["min_offer_age"]
            self._validate_constructor_arguments(min_offer_age)
            self.min_offer_age = min_offer_age
            for engine in sorted(self.engines, key=lambda _: random()):
                engine.min_offer_age = min_offer_age

    @property
    def trades(self):
        return _TradeLookerUpper(self.name)

    def __repr__(self):
        return f"<MarketAgent {self.name} {self.time_slot_str}>"
