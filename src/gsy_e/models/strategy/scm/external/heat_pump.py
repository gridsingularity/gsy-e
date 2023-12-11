from gsy_e.models.strategy.scm.external.forecast_mixin import SCMForecastExternalMixin
from gsy_e.models.strategy.scm.heat_pump import ScmHeatPumpStrategy


class ForecastScmHeatPumpStrategy(SCMForecastExternalMixin, ScmHeatPumpStrategy):
    """External SCM heat pump strategy"""

    def __init__(self, consumption_kWh_profile=None, consumption_kWh_profile_uuid=None):
        super().__init__(consumption_kWh_profile, consumption_kWh_profile_uuid)
        self.consumption_kWh_profile_uuid = consumption_kWh_profile_uuid
