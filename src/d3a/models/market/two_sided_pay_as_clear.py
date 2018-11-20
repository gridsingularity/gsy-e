from logging import getLogger
from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid

log = getLogger(__name__)


class TwoSidedPayAsClear(TwoSidedPayAsBid):

    def __init__(self, time_slot=None, area=None,
                 notification_listener=None, readonly=False):
        super().__init__(time_slot, area, notification_listener, readonly)

    def __repr__(self):  # pragma: no cover
        return "<TwoSidedPayAsClear{} offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>"\
            .format(" {}".format(self.time_slot_str),
                    len(self.offers),
                    sum(o.energy for o in self.offers.values()),
                    sum(o.price for o in self.offers.values()),
                    len(self.trades),
                    self.accumulated_trade_energy,
                    self.accumulated_trade_price
                    )
