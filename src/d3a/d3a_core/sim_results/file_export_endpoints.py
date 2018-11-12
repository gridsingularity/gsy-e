from slugify import slugify
from d3a.models.area import Area


class FileExportEndpoints:
    def __init__(self):
        self.trades = {}
        self.balancing_trades = {}
        self.stats = {}
        self.balancing_stats = {}
        self.buyer_trades = {}
        self.seller_trades = {}

    def _get_buyer_seller_trades(self, area: Area):
        """
        Determines the buy and sell rate of each leaf node
        """
        labels = ("slot", "rate [ct./kWh]", "energy [kWh]", "seller")
        for i, child in enumerate(area.children):
            for market in area.past_markets:
                for trade in market.trades:
                    buyer_slug = slugify(trade.buyer, to_lower=True)
                    seller_slug = slugify(trade.seller, to_lower=True)
                    if buyer_slug not in self.buyer_trades:
                        self.buyer_trades[buyer_slug] = dict((key, []) for key in labels)
                    if seller_slug not in self.seller_trades:
                        self.seller_trades[seller_slug] = dict((key, []) for key in labels)
                    else:
                        values = (market.time_slot,) + \
                                 (round(trade.offer.price / trade.offer.energy, 4),
                                  (trade.offer.energy * -1),) + \
                                 (slugify(trade.seller, to_lower=True),)
                        for ii, ri in enumerate(labels):
                            self.buyer_trades[buyer_slug][ri].append(values[ii])
                            self.seller_trades[seller_slug][ri].append(values[ii])
            if child.children:
                self._get_buyer_seller_trades(child)
