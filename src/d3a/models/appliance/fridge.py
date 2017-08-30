from d3a.models.appliance.mixins import SwitchableMixin
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.events import Trigger
from d3a.models.strategy.const import FRIDGE_TEMPERATURE, MAX_FRIDGE_TEMP, MIN_FRIDGE_TEMP, \
    FRIDGE_MIN_NEEDED_ENERGY


class FridgeAppliance(SwitchableMixin, SimpleAppliance):
    available_triggers = [
        Trigger('open', state_getter=lambda s: s.is_door_open,
                help="Open fridge door for 'duration' ticks."),
        Trigger('close', state_getter=lambda s: not s.is_door_open,
                help="Close fridge door immediately if open.")
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.temperature = FRIDGE_TEMPERATURE
        self.max_temperature = MAX_FRIDGE_TEMP
        self.min_temperature = MIN_FRIDGE_TEMP
        self.force_cool_energy = FRIDGE_MIN_NEEDED_ENERGY
        self.cooling_gain = 0
        self.door_open_loss = 0
        self.temp_change = 0
        self.is_door_open = False

    def event_activate(self):
        tick_length = self.area.config.tick_length.in_seconds()
        # If the fridge cools for the min needed energy it cools down 0.1C
        # This Value is taken from the Strategy/fridge.py file
        self.cooling_gain = - 0.05 * 2
        # Fridge with door open heats up 0.9C per minute
        self.door_open_loss = tick_length * (0.9 / 60)

    def report_energy(self, energy):
        if self.is_door_open:
            self.temp_change += self.door_open_loss

        if self.temperature + self.temp_change >= self.max_temperature:
            energy += self.force_cool_energy
            self.temp_change += self.cooling_gain

        super().report_energy(energy)

    def event_market_cycle(self):
        if self.owner:
            self.owner.strategy.post(temperature=self.temp_change)
        self.temperature = self.owner.strategy.fridge_temp
        self.temp_change = 0

    def trigger_open(self):
        self.is_door_open = True
        self.log.warning("Door opened")

    def trigger_close(self):
        self.is_door_open = False
        self.log.warning("Door closed")
