
class AreaStats:
    def __init__(self, area):
        self._accumulated_past_price = 0
        self._accumulated_past_energy = 0
        self._area = area

    def update_accumulated(self, markets):
        self._accumulated_past_price = sum(
            market.accumulated_trade_price
            for market in markets.values()
        )
        self._accumulated_past_energy = sum(
            market.accumulated_trade_energy
            for market in markets.values()
        )

    @property
    def _offer_count(self):
        return sum(
            len(m.offers)
            for markets in (self._area._markets.past_markets, self._area._markets.markets)
            for m in markets.values()
        )

    @property
    def _trade_count(self):
        return sum(
            len(m.trades)
            for markets in (self._area._markets.past_markets, self._area._markets.markets)
            for m in markets.values()
        )

    @property
    def historical_avg_rate(self):
        price = sum(
            market.accumulated_trade_price
            for market in self._area.all_markets
        ) + self._accumulated_past_price
        energy = sum(
            market.accumulated_trade_energy
            for market in self._area.all_markets
        ) + self._accumulated_past_energy
        return price / energy if energy else 0

    @property
    def historical_min_max_price(self):
        min_max_prices = [
            (m.min_trade_price, m.max_trade_price)
            for markets in (self._area._markets.past_markets, self._area._markets.markets)
            for m in markets.values()
        ]
        return (
            min(p[0] for p in min_max_prices),
            max(p[1] for p in min_max_prices)
        )

    def report_accounting(self, market, reporter, value, time=None):
        if time is None:
            time = self._area.now
        slot = market.time_slot
        if slot in self._area._markets.markets or slot in self._area._markets.past_markets:
            market.set_actual_energy(time, reporter, value)
        else:
            raise RuntimeError("Reporting energy for unknown market")

    @property
    def cheapest_offers(self):
        cheapest_offers = []
        for market in self._area.all_markets:
            cheapest_offers.extend(market.sorted_offers[0:1])
        return cheapest_offers
