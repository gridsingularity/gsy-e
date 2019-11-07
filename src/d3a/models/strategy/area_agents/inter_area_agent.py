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
from numpy.random import random
from d3a.models.strategy import BaseStrategy, _TradeLookerUpper
from d3a.constants import TIME_FORMAT
from d3a_interface.constants_limits import ConstSettings


class InterAreaAgent(BaseStrategy):
    parameters = ('owner', 'higher_market_or_id', 'lower_market_or_id', 'min_offer_age',
                  'time_slot')

    def __init__(self, *, engine_type, owner, higher_market_or_id, lower_market_or_id, time_slot,
                 min_offer_age=ConstSettings.IAASettings.MIN_OFFER_AGE):
        """
        :param min_offer_age: Minimum age of offer before transferring
        """
        super().__init__()
        self.owner = owner
        self._validate_constructor_arguments(min_offer_age)
        self.engines = [
            engine_type('High -> Low', higher_market_or_id, lower_market_or_id, min_offer_age,
                        self),
            engine_type('Low -> High', lower_market_or_id, higher_market_or_id, min_offer_age,
                        self),
        ]

        self.time_slot = time_slot.format(TIME_FORMAT)

        # serialization parameters
        self.higher_market = higher_market_or_id
        self.lower_market = lower_market_or_id
        self.min_offer_age = min_offer_age

    @staticmethod
    def _validate_constructor_arguments(min_offer_age):
        assert 0 <= min_offer_age <= 360

    def area_reconfigure_event(self, min_offer_age):
        self._validate_constructor_arguments(min_offer_age)
        self.min_offer_age = min_offer_age
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.min_offer_age = min_offer_age

    @property
    def trades(self):
        return _TradeLookerUpper(self.name)

    def __repr__(self):
        return "<InterAreaAgent {s.name} {s.time_slot}>".format(s=self)
