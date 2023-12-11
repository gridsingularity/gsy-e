from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy


class ScmHeatPumpStrategy(SCMLoadProfileStrategy):
    """Heat Pump SCM strategy with power consumption dictated by a profile."""

    def __init__(self, heat_pump_profile=None, heat_pump_profile_uuid=None):

        super().__init__(heat_pump_profile, heat_pump_profile_uuid)
        self.heat_pump_profile_uuid = heat_pump_profile_uuid
