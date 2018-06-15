import pathlib
import d3a

from d3a.models.strategy import ureg
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MIN_PV_SELLING_PRICE, \
    MAX_OFFER_TRAVERSAL_LENGTH
from d3a.models.strategy.mixins import ReadProfileMixin


d3a_path = d3a.__path__[0]


class PVPredefinedStrategy(ReadProfileMixin, PVStrategy):
    parameters = ('panel_count', 'risk', 'power_profile')

    def __init__(self, risk=DEFAULT_RISK, panel_count=1,
                 min_selling_price=MIN_PV_SELLING_PRICE, power_profile=None):
        super().__init__(panel_count=panel_count, risk=risk, min_selling_price=min_selling_price)
        self.power_profile = power_profile
        self._time_format = "%H:%M"

    def event_activate(self):
        # TODO: Need to have 2-stage initialization as well, because the area objects are not
        # created when the constructor is executed if we inherit from a mixin class,
        # therefore config cannot be read at that point
        if self.power_profile is None:
            self.power_profile = self.owner.config.cloud_coverage
        if self.power_profile == 0:  # 0:sunny
            profile_path = pathlib.Path(d3a_path + '/resources/Solar_Curve_W_sunny.csv')
        elif self.power_profile == 2:  # 2:partial
            profile_path = pathlib.Path(d3a_path + '/resources/Solar_Curve_W_partial.csv')
        elif self.power_profile == 1:  # 1:cloudy
            profile_path = pathlib.Path(d3a_path + '/resources/Solar_Curve_W_cloudy.csv')
        else:
            raise ValueError("Energy_profile has to be in [0,1,2]")

        # Populate energy production forecast data
        data = self.read_power_profile_to_energy(profile_path,
                                                 self._time_format,
                                                 self.area.config.slot_length)

        print("PV: " + str(data))

        for slot_time in [
            self.area.now + (self.area.config.slot_length * i)
            for i in range(
                (
                        self.area.config.duration
                        + (
                                self.area.config.market_count *
                                self.area.config.slot_length)
                ) // self.area.config.slot_length)
        ]:
            self.energy_production_forecast_kWh[slot_time] = \
                data[slot_time.format(self._time_format)]

        # TODO: A bit clumsy, but this decrease price calculation needs to be added here as well
        # Need to refactor once we convert the config object to a singleton that is shared globally
        # in the simulation
        self._decrease_price_every_nr_s = \
            (self.area.config.tick_length.seconds * MAX_OFFER_TRAVERSAL_LENGTH + 1) * ureg.seconds
