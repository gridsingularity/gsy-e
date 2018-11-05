from d3a.models.strategy import BaseStrategy, _TradeLookerUpper
from d3a import TIME_FORMAT


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

    @property
    def trades(self):
        return _TradeLookerUpper(self.name)

    def __repr__(self):
        return "<InterAreaAgent {s.name} {s.time_slot}>".format(s=self)
