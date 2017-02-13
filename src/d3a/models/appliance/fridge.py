from d3a.models.appliance.mixins import SwitchableMixin
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.events import Trigger
from d3a.models.strategy.const import FRIDGE_TEMPERATURE, MAX_FRIDGE_TEMP, MIN_FRIDGE_TEMP


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
        self.force_cool_energy = -0.05
        self.loss = 0
        self.cooling_gain = 0
        self.door_open_loss = 0
        self.is_door_open = False

    def event_activate(self):
        tick_length = self.area.config.tick_length.in_seconds()
        # Fridge loses 0.02C per minute
        self.loss = tick_length * (0.02 / 60)
        # If running cool 0.01C per second
        self.cooling_gain = tick_length * -0.01
        # Fridge with door open heats up 0.9C per minute
        self.door_open_loss = tick_length * (0.9 / 60)

    def report_energy(self, energy):
        temp_change = 0
        if self.is_door_open:
            temp_change += self.door_open_loss

        if energy:
            temp_change += self.cooling_gain
        else:
            temp_change += self.loss

        if self.temperature > self.max_temperature and not energy:
            energy = self.force_cool_energy
            temp_change += self.cooling_gain

        self.temperature += temp_change

        super().report_energy(energy)

    def event_market_cycle(self):
        self.temperature = self.owner.strategy.fridge_temp

    def trigger_open(self):
        self.is_door_open = True
        self.log.warning("Door opened")

    def trigger_close(self):
        self.is_door_open = False
        self.log.warning("Door closed")
