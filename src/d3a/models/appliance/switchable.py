from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.events import Trigger


class SwitchableAppliance(SimpleAppliance):
    available_triggers = [
        Trigger('on', state_getter=lambda s: s.on,
                help="Turn appliance on. Starts consuming energy."),
        Trigger('off', state_getter=lambda s: not s.on,
                help="Turn appliance off. Stops consuming energy.")
    ]

    def __init__(self, initially_on=True):
        super().__init__()
        self.on = initially_on

    def event_tick(self, *, area):
        if self.on:
            super().event_tick(area=area)

    def trigger_on(self):
        self.on = True
        self.log.warning("Turning on")

    def trigger_off(self):
        self.on = False
        self.log.warning("Turning off")
