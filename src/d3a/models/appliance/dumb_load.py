
from d3a.models.appliance.appliance import Appliance, ApplianceMode


class DumbLoad(Appliance):

    def __init__(self, name: str = "Dumb Load", report_freq: int = 1):
        super().__init__(name, report_freq)
        self.mode = ApplianceMode.OFF

    def power_on_appliance(self):
        self.change_mode_of_operation(ApplianceMode.ON)

    def power_off_appliance(self):
        self.change_mode_of_operation(ApplianceMode.OFF)

    def toggle_appliance(self):
        if self.mode is ApplianceMode.ON:
            self.power_off_appliance()
        else:
            self.power_on_appliance()
