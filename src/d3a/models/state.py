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

class PVState:
    def __init__(self):
        self.available_energy_kWh = defaultdict(lambda: 0)  # type: Dict[DateTime, float]


class LoadState:
    def __init__(self):
        self.desired_energy_Wh = defaultdict(lambda: 0)  # type: Dict[DateTime, float]


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
        if initial_soc is not None:
            if initial_capacity:
                strategy.log.warning("Ignoring initial_capacity parameter since "
                                     "initial_soc has also been given.")
            initial_capacity = capacity * initial_soc / 100
        self.capacity = capacity
        self.loss_per_hour = loss_per_hour
        self.max_abs_battery_power = max_abs_battery_power

        # storage capacity, that is already sold:
        self.pledged_sell_kWh = defaultdict(lambda: 0)  # type: Dict[DateTime, float]
        # storage capacity, that has been offered (but not traded yet):
        self.offered_sell_kWh = defaultdict(lambda: 0)  # type: Dict[DateTime, float]
        # energy, that has been bought:
        self.pledged_buy_kWh = defaultdict(lambda: 0)  # type: Dict[DateTime, float]
        # energy, that the storage wants to buy (but not traded yet):
        self.offered_buy_kWh = defaultdict(lambda: 0)  # type: Dict[DateTime, float]

        self.charge_history = defaultdict(lambda: '-')  # type: Dict[DateTime, float]
        self.charge_history_kWh = defaultdict(lambda: '-')  # type: Dict[DateTime, float]
        self.offered_history = defaultdict(lambda: '-')  # type: Dict[DateTime, float]
        self.used_history = defaultdict(lambda: '-')  # type: Dict[DateTime, float]
        self.energy_to_buy_dict = defaultdict(lambda: 0.)

        self._used_storage = initial_capacity
        self._battery_energy_per_slot = 0.0

    @property
    def used_storage(self):
        """
        Current stored energy
        """
        return self._used_storage

    def free_storage(self, time_slot):
        """
        Storage, that has not been promised or occupied
        """
        in_use = self._used_storage \
            - self.pledged_sell_kWh[time_slot] \
            + self.pledged_buy_kWh[time_slot] \
            + self.offered_buy_kWh[time_slot]
        return self.capacity - in_use

    def max_offer_energy_kWh(self, time_slot):
        return self.used_storage - self.pledged_sell_kWh[time_slot] \
                                 - self.offered_sell_kWh[time_slot]

    def max_buy_energy_kWh(self, time_slot):
        return self.capacity - (self.used_storage
                                + self.pledged_buy_kWh[time_slot]
                                + self.offered_buy_kWh[time_slot])

    def set_battery_energy_per_slot(self, slot_length):
        self._battery_energy_per_slot = self.max_abs_battery_power * \
                                        (slot_length / duration(hours=1))

    def has_battery_reached_max_power(self, energy, time_slot):
        return abs(energy
                   + self.pledged_sell_kWh[time_slot]
                   + self.offered_sell_kWh[time_slot]
                   - self.pledged_buy_kWh[time_slot]
                   - self.offered_buy_kWh[time_slot]) > \
               self._battery_energy_per_slot

    def clamp_energy_to_sell_kWh(self, market_slot_time_list):
        """
        Determines available energy to sell for each active market and returns a dict[TIME, FLOAT]
        """
        accumulated_pledged = 0
        accumulated_offered = 0
        for time_slot in market_slot_time_list:
            accumulated_pledged += self.pledged_sell_kWh[time_slot]
            accumulated_offered += self.offered_sell_kWh[time_slot]
        energy = round((self.used_storage - accumulated_pledged - accumulated_offered) /
                       len(market_slot_time_list), 10)

        storage_dict = {}
        for time_slot in market_slot_time_list:
            clamped_energy = min(energy, self.max_offer_energy_kWh(time_slot),
                                 self._battery_energy_per_slot)
            target_soc = (self.used_storage - self.pledged_sell_kWh[time_slot] -
                          self.offered_sell_kWh[time_slot] - clamped_energy) / self.capacity
            if ConstSettings.STORAGE_MIN_ALLOWED_SOC > target_soc:
                clamped_energy = max(0, self.used_storage + self.pledged_sell_kWh[time_slot] -
                                     self.offered_sell_kWh[time_slot] -
                                     self.capacity * ConstSettings.STORAGE_MIN_ALLOWED_SOC)

            storage_dict[time_slot] = clamped_energy

        return storage_dict

    def clamp_energy_to_buy_kWh(self, market_slot_time_list):
        """
        Determines amount of energy that can be bought for each active market and writes it to
        self.energy_to_buy_dict
        """

        accumulated_bought = 0
        accumulated_sought = 0
        for time_slot in market_slot_time_list:
            accumulated_bought += self.pledged_buy_kWh[time_slot]
            accumulated_sought += self.offered_buy_kWh[time_slot]
        energy = round((self.capacity
                        - self.used_storage
                        - accumulated_bought
                        - accumulated_sought) / len(market_slot_time_list), 10)

        for time_slot in market_slot_time_list:
            clamped_energy = min(energy, self.max_buy_energy_kWh(time_slot),
                                 self._battery_energy_per_slot)

            self.energy_to_buy_dict[time_slot] = clamped_energy

    def check_state(self, time_slot):
        """
        Sanity check of the state variables.
        """
        charge = 100.0 * self.used_storage / self.capacity
        assert 0 <= round(charge, 10) <= 100
        assert 0 <= round(self.offered_sell_kWh[time_slot], 10) <= self.capacity
        assert 0 <= round(self.pledged_sell_kWh[time_slot], 10) <= self.capacity
        assert 0 <= round(self.pledged_buy_kWh[time_slot], 10) <= self.capacity
        assert 0 <= round(self.offered_buy_kWh[time_slot], 10) <= self.capacity

    def lose(self, proportion):
        self._used_storage *= 1.0 - proportion

    def tick(self, area, time_slot):
        self.check_state(time_slot)
        self.lose(self.loss_per_hour * area.config.tick_length.in_seconds() / 3600)

    def market_cycle(self, past_time_slot, time_slot):
        """
        Simulate actual Energy flow by removing pledged storage and added baought energy to the
        used_storage
        """
        self._used_storage -= self.pledged_sell_kWh[past_time_slot]
        self._used_storage += self.pledged_buy_kWh[past_time_slot]

        self.charge_history[time_slot] = 100.0 * self.used_storage / self.capacity
        self.charge_history_kWh[time_slot] = self.used_storage
        self.offered_history[time_slot] = self.offered_sell_kWh[time_slot]
