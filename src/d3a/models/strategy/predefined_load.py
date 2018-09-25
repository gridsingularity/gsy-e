"""
Create a load that uses a profile as input for its power values
"""
import sys
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.read_user_profile import read_arbitrary_profile
from d3a.models.strategy.read_user_profile import InputProfileTypes


class DefinedLoadStrategy(LoadHoursStrategy):
    """
        Strategy for creating a load profile. It accepts as an input a load csv file or a
        dictionary that contains the load values for each time point
    """
    parameters = ('daily_load_profile', 'max_energy_rate')

    def __init__(self, daily_load_profile, max_energy_rate: float =sys.maxsize):
        """
        Constructor of DefinedLoadStrategy
        :param daily_load_profile: input profile for a day. Can be either a csv file path,
        or a dict with hourly data (Dict[int, float])
        or a dict with arbitrary time data (Dict[str, float])
        :param max_energy_rate: max energy rate of the offers that the load can
        accept
        """
        super().__init__(0, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                         max_energy_rate=max_energy_rate)
        self.daily_load_profile = daily_load_profile
        self.load_profile = {}

    def event_activate(self):
        """
        Runs on activate event. Reads the power profile data and calculates the required energy
        for each slot.
        :return: None
        """
        self.load_profile = read_arbitrary_profile(
            InputProfileTypes.POWER,
            self.daily_load_profile,
            slot_length=self.area.config.slot_length)
        self._update_energy_requirement()

    def _update_energy_requirement(self):
        """
        Update required energy values for each market slot.
        :return: None
        """
        self.energy_requirement_Wh = 0
        if self.load_profile[self.area.next_market.time_slot_str] != 0:
            # TODO: Refactor energy_requirement_Wh to denote unit Wh
            self.energy_requirement_Wh = \
                self.load_profile[self.area.next_market.time_slot_str] * 1000.0
        self.state.record_desired_energy(self.area, self.energy_requirement_Wh)

    def _operating_hours(self, energy):
        """
        Disabled feature for this subclass
        """
        return 0

    def _allowed_operating_hours(self, time):
        """
        Disabled feature for this subclass
        """
        return True
