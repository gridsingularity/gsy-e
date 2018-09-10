from collections import defaultdict
from pendulum import duration

from d3a.models.strategy.const import ConstSettings


# Complex device models should be split in three classes each:
#
# - a strategy class responsible for buying/selling options
# - an appliance class responsible for actual energy transfers (drawing/serving options)
# - a state class keeping the state of the appliance
#
# The full three-classes setup is not necessary for every device:
# - Some devices may not have a state. The state class is mainly meant to share data between
#   strategy and appliance, so simple responses to triggers and events are not part of it,
#   neither are unpredictable parameters that the strategy cannot take into account (like
#   cloud_cover in PVAppliance)
# - If a device has no state, maybe it doesn't need its own appliance class either;
#   SimpleAppliance may do.


class LoadState:
    def __init__(self):
        self.desired_energy = defaultdict(lambda: 0)

    def record_desired_energy(self, area, energy):
        time_slot = area.next_market.time_slot
        self.desired_energy[time_slot] = energy


class FridgeState:
    def __init__(self):
        self.temperature = ConstSettings.FRIDGE_TEMPERATURE
        self.temp_history = defaultdict(lambda: '-')
        self.min_temperature = ConstSettings.MIN_FRIDGE_TEMP
        self.max_temperature = ConstSettings.MAX_FRIDGE_TEMP

    @property
    def normalized_temperature(self):
        # between -1 (min_temperature) and +1 (max_temperature)

        domain = self.max_temperature - self.min_temperature
        center = 0.5 * (self.max_temperature + self.min_temperature)
        return 2 * (self.temperature - center) / domain

    def market_cycle(self, area):
        self.temp_history[area.current_market.time_slot] = self.temperature

    def tick(self, area):
        # The not cooled fridge warms up (0.02 / 60)C up every second
        self.temperature += area.config.tick_length.in_seconds() * round((0.02 / 60), 6)


class StorageState:
    def __init__(self,
                 initial_capacity=0.0,
                 initial_soc=None,
                 capacity=ConstSettings.STORAGE_CAPACITY,
                 max_abs_battery_power=ConstSettings.MAX_ABS_BATTERY_POWER,
                 loss_per_hour=0.01,
                 strategy=None):
        self._blocked_storage = 0.0
        self._offered_storage = 0.0
        self._battery_energy_per_slot = 0.0
        if initial_soc is not None:
            if initial_capacity:
                strategy.log.warning("Ignoring initial_capacity parameter since "
                                     "initial_soc has also been given.")
            initial_capacity = capacity * initial_soc / 100
        self._used_storage = initial_capacity
        self.capacity = capacity
        self.max_abs_battery_power = max_abs_battery_power
        self.loss_per_hour = loss_per_hour
        self.offered_history = defaultdict(lambda: '-')
        self.used_history = defaultdict(lambda: '-')
        self.charge_history = defaultdict(lambda: '-')
        self.charge_history_kWh = defaultdict(lambda: '-')
        self._traded_energy_per_slot = defaultdict(lambda: 0.0)  # type: Dict[DateTime, float]

    @property
    def blocked_storage(self):
        return self._blocked_storage

    @property
    def offered_storage(self):
        return self._offered_storage

    @property
    def used_storage(self):
        return self._used_storage

    @property
    def free_storage(self):
        in_use = self._blocked_storage + self._offered_storage + self._used_storage
        return self.capacity - in_use

    def market_cycle(self, area):
        self.used_history[area.current_market.time_slot] = self._used_storage
        self.offered_history[area.current_market.time_slot] = self._offered_storage
        charge = 100.0 * (self._used_storage + self._offered_storage) / self.capacity
        self.charge_history[area.current_market.time_slot] = charge
        self.charge_history_kWh[area.current_market.time_slot] = \
            self._used_storage + self._offered_storage

    def tick(self, area):
        self.lose(self.loss_per_hour * area.config.tick_length.in_seconds() / 3600)
        free = self.free_storage / self.capacity
        if free < 0.2:
            area.log.info("Storage reached more than 80% Battery: {}%".format(
                str((1 - free) * 100)))

    def set_battery_energy_per_slot(self, slot_length):
        self._battery_energy_per_slot = self.max_abs_battery_power * \
                                        (slot_length/duration(hours=1))

    def has_battery_reached_max_power(self, time_slot):
        return abs(self.traded_energy_per_slot(time_slot)) >= \
               self._battery_energy_per_slot

    def clamp_energy_to_buy_kWh(self, energy=None):
        # If no energy is passed, try to buy energy to fill up the battery
        if energy is None:
            energy = self.free_storage
        return min(self._battery_energy_per_slot, self.free_storage, energy)

    def clamp_energy_to_sell_kWh(self, energy, time_slot):
        # If no energy is passed, try to sell all the Energy left in the storage
        if energy is None:
            energy = self.used_storage

        # Limit energy according to the maximum battery power
        clamped_energy = min(energy,
                             (self._battery_energy_per_slot -
                              self.traded_energy_per_slot(time_slot)))
        # Limit energy to respect minimum allowed battery SOC
        target_soc = (self.used_storage + self.offered_storage - clamped_energy) / self.capacity
        if ConstSettings.STORAGE_MIN_ALLOWED_SOC > target_soc:
            clamped_energy = self.used_storage + self.offered_storage - \
                             self.capacity * ConstSettings.STORAGE_MIN_ALLOWED_SOC
        return clamped_energy

    def traded_energy_per_slot(self, slot):
        return self._traded_energy_per_slot[slot]

    # it increase positively while charging and negatively while discharging
    def update_energy_per_slot(self, energy, slot):
        self._traded_energy_per_slot[slot] += energy

    def block_storage(self, energy):
        self._blocked_storage += energy

    def offer_storage(self, energy):
        assert energy <= self._used_storage + 1e-6, 'Used storage exceeded.'
        self._used_storage -= energy
        self._offered_storage += energy

    def fill_blocked_storage(self, energy):
        assert energy <= self._blocked_storage + 1e-6, 'Blocked storage exceeded.'
        self._blocked_storage -= energy
        self._used_storage += energy

    def sold_offered_storage(self, energy):
        assert energy <= self._offered_storage + 1e-6, 'Sale exceeds offered storage.'
        self._offered_storage -= energy

    def lose(self, proportion):
        self._used_storage *= 1.0 - proportion

    def remove_offered(self, energy):
        assert energy <= self._offered_storage + 1e-6, 'Offered storage exceeded.'
        self._offered_storage -= energy
        self._used_storage += energy
