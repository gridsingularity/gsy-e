from d3a.exceptions import MarketException
from d3a.models.events import Trigger
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.storage import StorageStrategy


class ECarStrategy(StorageStrategy):
    available_triggers = [
        Trigger('arrive', state_getter=lambda s: s.connected_to_grid,
                help="E-Car arrives and starts participating in market"),
        Trigger('depart', state_getter=lambda s: not s.connected_to_grid,
                help="E-Car departs and stops participating in market"),
    ]

    parameters = ('risk', 'arrival_time', 'depart_time', 'initial_capacity',
                  'initial_charge', 'battery_capacity')

    def __init__(self, risk=ConstSettings.DEFAULT_RISK, initial_capacity=0.0, initial_charge=None,
                 initial_rate_option=ConstSettings.INITIAL_ESS_RATE_OPTION,
                 energy_rate_decrease_option=ConstSettings.ESS_RATE_DECREASE_OPTION,
                 energy_rate_decrease_per_update=ConstSettings.ENERGY_RATE_DECREASE_PER_UPDATE,
                 battery_capacity=ConstSettings.STORAGE_CAPACITY,
                 arrival_time=ConstSettings.ARRIVAL_TIME, depart_time=ConstSettings.DEPART_TIME):
        if arrival_time is None:
            arrival_time = ConstSettings.ARRIVAL_TIME
        if depart_time is None:
            depart_time = ConstSettings.DEPART_TIME
        if not 0 <= arrival_time <= 23 or not 0 <= depart_time <= 23:
            raise ValueError("Depart_time and arrival_time should be between 0 and 23.")
        if not arrival_time < depart_time:
            raise ValueError("Arrival time should be less than depart time.")
        super().__init__(risk, initial_capacity, initial_charge,
                         initial_rate_option, energy_rate_decrease_option,
                         energy_rate_decrease_per_update, battery_capacity)
        self.arrival_time = arrival_time
        self.depart_time = depart_time
        self.connected_to_grid = False

    def event_tick(self, *, area):
        current_time = self.area.now.hour
        if not self.connected_to_grid:
            # Car arrives at charging station at
            if self.arrival_time == current_time:
                self.arrive()

        if self.connected_to_grid:
            # Car departs from charging station at
            if current_time == self.depart_time:
                self.depart()

        if not self.connected_to_grid:
            # This means the car is driving around some where
            self.state.lose(0.0001)
            return
        # Check if there are cheap offers to buy
        self.buy_energy()
        # Check if any energy from the Car can be sold
        # Same process as Storage
        self.sell_energy()

    def arrive(self):
        self.log.info("E-Car arrived")
        self.connected_to_grid = True
        self.sell_energy(energy=self.state.used_storage)

    trigger_arrive = arrive

    def _remove_offers_on_depart(self):
        for offer, market in self.offers.posted.items():
            try:
                market.delete_offer(offer.id)
                self.state.remove_offered(offer.energy)
            except MarketException:
                continue

    def depart(self):
        self._remove_offers_on_depart()
        self.connected_to_grid = False
        self.log.info("E-Car departs")

    trigger_depart = depart

    def event_market_cycle(self):
        if self.connected_to_grid:
            super().event_market_cycle()
