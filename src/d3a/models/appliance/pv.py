from pendulum import Interval

from d3a.models.appliance.builder import get_pv_curves
from d3a.models.appliance.properties import ElectricalProperties
from d3a.models.appliance.appliance import Appliance, ApplianceMode, EnergyCurve
from d3a.models.events import Trigger


PANEL_COUNT_AUTO = object()


class PVAppliance(Appliance):
    available_triggers = [
        Trigger('cloud_cover', {'percent': float, 'duration': int},
                help="Set cloud cover to 'percent' for 'duration' ticks.")
    ]

    def __init__(self, name: str = "PV", report_freq: int = 1,
                 panel_count: int = PANEL_COUNT_AUTO):
        super().__init__(name, report_freq)
        self.cloud_duration = 0
        self.multiplier = 1.0
        self.panel_count = panel_count
        self.report_sign = 1              # As PV produces energy

    def event_activate(self):
        if self.panel_count is PANEL_COUNT_AUTO:
            if self.owner.strategy and self.owner.strategy.panel_count:
                self.panel_count = self.owner.strategy.panel_count
            else:
                self.panel_count = 1
        mode_curve_data = get_pv_curves(self.panel_count)
        energy_curve = EnergyCurve(
            ApplianceMode.ON,
            mode_curve_data[ApplianceMode.ON],
            Interval(minutes=5),
            self.area.config.tick_length
        )
        energy_curve.add_mode_curve(ApplianceMode.OFF, mode_curve_data[ApplianceMode.OFF])
        self.electrical_properties = ElectricalProperties(
            (min(mode_curve_data[ApplianceMode.ON]), max(mode_curve_data[ApplianceMode.ON])),
            (0, 0)
        )
        self.energy_curve = energy_curve
        self.start_appliance()

    def handle_cloud_cover(self, percent: float = 0, duration: int = 0):
        """
        Method to introduce cloud cover over PV. PV will produce 0 W during cloud cover.
        :param percent: Cloud cover between 0 - 100%.
        :param duration: duration of cloud cover in ticks.
        """

        percent = float(percent)
        duration = int(duration)
        self.cloud_duration = duration
        # 2% residual power generated even under 100% cloud cover
        self.multiplier = (1 - percent / 100) if percent < 98 else 0.02
        if self.cloud_duration <= 0 or percent <= 0:
            self.end_cloud_cover()
            self.log.warning("Cloud cover ended")
        else:
            self.log.warning("%0.1f cloud cover starting for %d ticks", percent, duration)

    # Alias for trigger
    trigger_cloud_cover = handle_cloud_cover

    def end_cloud_cover(self):
        """
        Immediately ends cloud cover
        """
        self.multiplier = 1.0
        self.cloud_duration = 0

    def get_current_power(self):
        power = self.usageGenerator.get_reading_at(self.area.current_tick)
        if power is None:
            power = 0

        power *= self.multiplier

        return round(power, 6)

    def event_tick(self, *, area):
        if self.cloud_duration > 0:
            self.cloud_duration -= 1
            if self.cloud_duration == 0:
                self.log.warning("Cloud cover ended")
        else:
            self.multiplier = 1.0

        # +ve for produced energy
        energy = self.get_current_power()
        if not energy:
            return

        self.last_reported_tick += 1

        if self.last_reported_tick >= self.report_frequency:
            # report power generation/consumption to area
            self.last_reported_tick = 0
            energy_balance = self.get_tick_energy_balance(self.report_frequency)
            if round(energy, 3) > round(energy_balance, 3):
                # Supply only the amount approved in trade
                energy = energy_balance

            self.report_energy(area, energy)
