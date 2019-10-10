"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from d3a.models.appliance.mixins import SwitchableMixin
from d3a.models.appliance.simple import SimpleAppliance
from d3a.events.event_structures import Trigger


class PVAppliance(SwitchableMixin, SimpleAppliance):
    available_triggers = [
        Trigger('cloud_cover', {'percent': float, 'duration': int},
                help="Set cloud cover to 'percent' for 'duration' ticks.")
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cloud_duration = 0
        # 1 equals 100% sunshine while 0 equals no sunshine and full cloud cover
        self.cloud_cover = 1

    def report_energy(self, energy):
        if self.cloud_duration != 0:
            self.cloud_duration -= 1
            if self.cloud_duration == 0:
                self.log.info("Cloud cover ended")
            if self.cloud_cover < 1:
                super().report_energy(energy=energy * self.cloud_cover)

        else:
            super().report_energy(energy=energy)

    def trigger_cloud_cover(self, percent: float = 0, duration: int = -1):
        self.cloud_cover = (1 - percent / 100) if percent < 98 else 0.02
        if duration != -1:
            self.cloud_duration = duration
