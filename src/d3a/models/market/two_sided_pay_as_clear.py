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
from logging import getLogger
from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid
from d3a.models.state import MarketClearingState

log = getLogger(__name__)


class TwoSidedPayAsClear(TwoSidedPayAsBid):

    def __init__(self, time_slot=None, area=None,
                 notification_listener=None, readonly=False):
        super().__init__(time_slot, area, notification_listener, readonly)
        self.state = MarketClearingState()
        self.cumulative_offers = dict()  # type Dict[Datetime, dict(]
        self.cumulative_bids = dict()  # type Dict[Datetime, dict(]

    def __repr__(self):  # pragma: no cover
        return "<TwoSidedPayAsClear{} bids: {} (E: {} kWh V:{}) " \
               "offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>"\
            .format(" {}".format(self.time_slot_str),
                    len(self.bids),
                    sum(b.energy for b in self.bids.values()),
                    sum(b.price for b in self.bids.values()),
                    len(self.offers),
                    sum(o.energy for o in self.offers.values()),
                    sum(o.price for o in self.offers.values()),
                    len(self.trades),
                    self.accumulated_trade_energy,
                    self.accumulated_trade_price
                    )
