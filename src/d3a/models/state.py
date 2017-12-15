from collections import defaultdict

from d3a.models.strategy.const import FRIDGE_TEMPERATURE


class FridgeState:
    def __init__(self):
        self.temperature = FRIDGE_TEMPERATURE
        self.temp_history = defaultdict(lambda: '-')
        self.min_temperature = 0
        self.max_temperature = 0
