from gsy_e.models.strategy.scm.external.forecast_mixin import SCMForecastExternalMixin
from gsy_e.models.strategy.scm.heat_pump import ScmHeatPumpStrategy


class ForecastScmHeatPumpStrategy(SCMForecastExternalMixin, ScmHeatPumpStrategy):
    """External SCM heat pump strategy"""

    def __init__(self, heat_pump_profile=None, heat_pump_profile_uuid=None):
        super().__init__(heat_pump_profile, heat_pump_profile_uuid)
        self.heat_pump_profile_uuid = heat_pump_profile_uuid
