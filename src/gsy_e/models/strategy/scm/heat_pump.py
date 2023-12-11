from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy


class ScmHeatPumpStrategy(SCMLoadProfileStrategy):
    """Heat Pump SCM strategy with power consumption dictated by a profile."""

    def __init__(self, consumption_kWh_profile=None, consumption_kWh_profile_uuid=None):

        super().__init__(consumption_kWh_profile, consumption_kWh_profile_uuid)
        self.consumption_kWh_profile_uuid = consumption_kWh_profile_uuid
