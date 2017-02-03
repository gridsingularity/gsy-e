from logging import getLogger
from d3a.models.area import Area
from d3a.models.appliance.appliance import Appliance

log = getLogger(__name__)


class PVAppliance(Appliance):

    def __init__(self, name: str = "PV", report_freq: int = 1, panel_count: int = 1):
        super().__init__(name, report_freq)
        self.cloud_duration = 0
        self.multiplier = 1.0
        self.panel_count = panel_count
        self.report_sign = 1              # As PV produces energy

    def handle_cloud_cover(self, percent: float = 0, duration: int = 0):
        """
        Method to introduce cloud cover over PV. PV will produce 0 W during cloud cover.
        :param percent: Cloud cover between 0 - 100%.
        :param duration: duration of cloud cover in ticks.
        """
        self.cloud_duration = duration
        # 2% residual power generated even under 100% cloud cover
        self.multiplier = (1 - percent / 100) if percent < 98 else 0.02
        if self.cloud_duration <= 0:
            self.end_cloud_cover()

    def end_cloud_cover(self):
        """
        Immediately ends cloud cover
        """
        self.multiplier = 1.0
        self.cloud_duration = 0

    def get_current_power(self):
        power = self.usageGenerator.get_reading_at(self.get_time_in_sec())
        if power is None:
            power = 0

        power *= self.multiplier

        return round(power, 2)

    def event_tick(self, *, area: Area):
        if self.cloud_duration > 0:
            self.cloud_duration -= 1
        else:
            self.multiplier = 1.0

        # +ve for produced energy
        energy = self.usageGenerator.get_reading_at(self.get_time_in_sec())

        self.last_reported_tick += 1

        if self.last_reported_tick >= self.report_frequency:
            # report power generation/consumption to area
            self.last_reported_tick = 0
            energy_balance = self.get_energy_balance()
            if round(energy, 3) > round(energy_balance, 3):
                # Supply only the amount approved in trade
                energy = energy_balance

            self.report_energy(area, energy)
