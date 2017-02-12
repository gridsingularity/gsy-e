from d3a.exceptions import MarketException
from d3a.models.events import Trigger
from d3a.models.strategy.const import DEFAULT_RISK, ARRIVAL_TIME, DEPART_TIME
from d3a.models.strategy.storage import StorageStrategy


class ECarStrategy(StorageStrategy):
    available_triggers = [
        Trigger('arrive', state_getter=lambda s: s.connected_to_grid,
                help="E-Car arrives and starts participating in market"),
        Trigger('depart', state_getter=lambda s: not s.connected_to_grid,
                help="E-Car departs and stops participating in market"),
    ]

    def __init__(self, risk=DEFAULT_RISK, arrival_time=ARRIVAL_TIME, depart_time=DEPART_TIME):
        super().__init__(risk)
        self.arrival_time = arrival_time
        self.depart_time = depart_time
        self.connected_to_grid = False

    def event_tick(self, *, area):
        if self.arrival_time is not None:
            arrival_time = self.area.now.start_of("day").hour_(self.arrival_time)
            # Car arrives at charging station at
            if self.area.now.diff(arrival_time).in_minutes() == 0:
                self.arrive()

        if self.depart_time is not None:
            depart_time = self.area.now.start_of("day").hour_(self.depart_time)
            # Car departs from charging station at
            if self.area.now.diff(depart_time).in_minutes() == 0:
                self.depart()

        if not self.connected_to_grid:
            # This means the car is driving around some where
            self.used_storage *= 0.9999
            return
        # Taking the cheapest offers in every market currently open and building the average
        # Same process as storage
        avg_cheapest_offer_price = self.find_avg_cheapest_offers()
        # Check if there are cheap offers to buy
        self.buy_energy(avg_cheapest_offer_price)
        # Check if any energy from the Car can be sold
        # Same process as Storage
        self.sell_energy(avg_cheapest_offer_price)

    def arrive(self):
        self.log.warning("E-Car arrived")
        self.connected_to_grid = True
        self.sell_energy(self.used_storage)

    trigger_arrive = arrive

    def depart(self):
        for market, offers in self.offers_posted.items():
            for offer in offers:
                try:
                    market.delete_offer(offer.id)
                    self.used_storage += offer.energy
                except MarketException:
                    continue
        self.connected_to_grid = False
        self.log.warning("E-Car departs")

    trigger_depart = depart
