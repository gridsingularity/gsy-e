from d3a.models.appliance.mixins import SwitchableMixin
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.events import Trigger
from d3a.models.strategy.const import ConstSettings


class FridgeAppliance(SwitchableMixin, SimpleAppliance):
    available_triggers = [
        Trigger('open', state_getter=lambda s: s.is_door_open,
                help="Open fridge door for 'duration' ticks."),
        Trigger('close', state_getter=lambda s: not s.is_door_open,
                help="Close fridge door immediately if open.")
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = None
        self.force_cool_energy = - ConstSettings.FridgeSettings.MIN_NEEDED_ENERGY
        self.cooling_gain = 0
        self.door_open_loss = 0
        self.temp_change = 0
        self.is_door_open = False

    @property
    def temperature(self):
        return self.state.temperature if self.state else None

    def event_activate(self):
        self.state = self.owner.strategy.state
        tick_length = self.area.config.tick_length.in_seconds()
        # If the fridge cools for the min needed energy it cools down 0.1C
        # This Value is taken from the Strategy/fridge.py file
        self.cooling_gain = - tick_length * 0.05 * 2
        # Fridge with door open heats up 0.9C per minute
        self.door_open_loss = tick_length * (0.9 / 60)
        # Need to multiply energy with tick length because the full tick will be cooled
        # And / 1000 to get kWh
        self.force_cool_energy *= tick_length / 1000

    def report_energy(self, energy):
        # This happens every tick
        if self.is_door_open:
            self.temp_change += self.door_open_loss

        if self.state.temperature + self.temp_change >= self.state.max_temperature:
            energy += self.force_cool_energy
            self.temp_change += self.cooling_gain

        super().report_energy(energy)

    def event_market_cycle(self):
        if self.state:
            self.state.temperature += self.temp_change
        self.temp_change = 0

    def trigger_open(self):
        self.is_door_open = True
        self.log.warning("Door opened")

    def trigger_close(self):
        self.is_door_open = False
        self.log.warning("Door closed")
