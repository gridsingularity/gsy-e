from collections import defaultdict

from d3a.models.strategy.const import FRIDGE_TEMPERATURE, MAX_FRIDGE_TEMP, MIN_FRIDGE_TEMP


# Complex device models should be split in three classes each:
#
# - a strategy class responsible for buying/selling options
# - an appliance class responsible for actual energy transfers (drawing/serving options)
# - a state class keeping the state of the appliance
#
# Some devices may not have a state and/or the SimpleAppliance class may be enough for them.


class FridgeState:
    def __init__(self):
        self.temperature = FRIDGE_TEMPERATURE
        self.temp_history = defaultdict(lambda: '-')
        self.min_temperature = MIN_FRIDGE_TEMP
        self.max_temperature = MAX_FRIDGE_TEMP

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
