import sys
import os
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.mixins import ReadProfileMixin


class DefinedLoadStrategy(ReadProfileMixin, LoadHoursStrategy):
    """
        Strategy for creating a load profile. It accepts as an input a load csv file or a
        dictionary that contains the load values for each time point
    """
    parameters = ('load_profile', 'acceptable_energy_rate')

    def __init__(self, daily_load_profile, acceptable_energy_rate=sys.maxsize):
        super().__init__(0, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                         acceptable_energy_rate=acceptable_energy_rate)
        self.daily_load_profile = daily_load_profile
        self.load_profile = {}

    def event_activate(self):
        if os.path.isfile(self.daily_load_profile):
            self.load_profile = self.read_power_profile_to_energy(
                self.daily_load_profile,
                "%H:%M",
                self.area.config.slot_length
            )
        elif isinstance(self.daily_load_profile, dict):
            self.load_profile = self.interpolate_profile_data_for_market_slot(
                self.daily_load_profile,
                "%H:%M",
                self.area.config.slot_length
            )
        else:
            raise TypeError("Unsupported type for load strategy input: " +
                            str(self.daily_load_profile))
        self._update_energy_requirement()

    def _update_energy_requirement(self):
        self.energy_requirement = 0
        if self.load_profile[self.area.next_market.time_slot.format('%H:%M')] != 0:
            energy_per_slot = self.load_profile[self.area.next_market.time_slot.format('%H:%M')]
            self.energy_requirement = energy_per_slot
        self.state.record_desired_energy(self.area, self.energy_requirement)

    def _operating_hours(self, energy):
        # Disable operating hours calculation
        return 0

    def _allowed_operating_hours(self, time):
        return True
