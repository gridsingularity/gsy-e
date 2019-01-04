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
from d3a.models.strategy import BaseStrategy, _TradeLookerUpper
from d3a.constants import TIME_FORMAT
from d3a.models.const import ConstSettings


class InterAreaAgent(BaseStrategy):
    parameters = ('owner', 'higher_market', 'lower_market', 'transfer_fee_pct',
                  'min_offer_age')

    def __init__(self, *, engine_type, owner, higher_market, lower_market,
                 transfer_fee_pct=1, min_offer_age=1):
        """
        Equalize markets

        :param higher_market:
        :type higher_market: Market
        :param lower_market:
        :type lower_market: Market
        :param min_offer_age: Minimum age of offer before transferring
        """
        super().__init__()
        self.owner = owner

        if ConstSettings.IAASettings.PRICING_SCHEME != 0:
            transfer_fee_pct = 0

        self._validate_constructor_arguments(transfer_fee_pct, min_offer_age)

        self.engines = [
            engine_type('High -> Low', higher_market, lower_market, min_offer_age,
                        transfer_fee_pct, self),
            engine_type('Low -> High', lower_market, higher_market, min_offer_age,
                        transfer_fee_pct, self),
        ]

        self.time_slot = higher_market.time_slot.strftime(TIME_FORMAT)

        # serialization parameters
        self.higher_market = higher_market
        self.lower_market = lower_market
        self.transfer_fee_pct = transfer_fee_pct
        self.min_offer_age = min_offer_age

    def _validate_constructor_arguments(self, transfer_fee_pct, min_offer_age):
        assert 0 <= transfer_fee_pct <= 100
        assert 1 <= min_offer_age <= 360

    def area_reconfigure_event(self, transfer_fee_pct, min_offer_age):
        self._validate_constructor_arguments(transfer_fee_pct, min_offer_age)
        self.transfer_fee_pct = transfer_fee_pct
        self.min_offer_age = min_offer_age
        for engine in self.engines:
            engine.transfer_fee_pct = transfer_fee_pct
            engine.min_offer_age = min_offer_age

    @property
    def trades(self):
        return _TradeLookerUpper(self.name)

    def __repr__(self):
        return "<InterAreaAgent {s.name} {s.time_slot}>".format(s=self)
