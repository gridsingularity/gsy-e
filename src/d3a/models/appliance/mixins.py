from d3a.events.event_structures import Trigger


class SwitchableMixin:
    available_triggers = [
        Trigger('on', state_getter=lambda s: s.is_on,
                help="Turn appliance on. Starts consuming energy."),
        Trigger('off', state_getter=lambda s: not s.is_on,
                help="Turn appliance off. Stops consuming energy.")
    ]

    parameters = ('initially_on',)

    def __init__(self, *args, initially_on=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_on = initially_on
        self.initially_on = initially_on

    def trigger_on(self):
        self.is_on = True
        self.log.warning("Turning on")

    def trigger_off(self):
        self.is_on = False
        self.log.warning("Turning off")
