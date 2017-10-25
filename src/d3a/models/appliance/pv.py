from d3a.models.appliance.mixins import SwitchableMixin
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.events import Trigger


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
                self.log.warning("Cloud cover ended")
            if self.cloud_cover < 1:
                super().report_energy(energy=energy * self.cloud_cover)

        else:
            super().report_energy(energy=energy)

    def trigger_cloud_cover(self, percent: float = 0, duration: int = -1):
        self.cloud_cover = (1 - percent / 100) if percent < 98 else 0.02
        if duration != -1:
            self.cloud_duration = duration
