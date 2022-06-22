from gsy_e.models.strategy.external_strategies import ExternalMixin
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy


class SmartMeterExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the SmartMeter strategies.
    Should always be inherited together with a superclass of SmartMeterStrategy.
    """


class SmartMeterExternalStrategy(SmartMeterExternalMixin, SmartMeterStrategy):
    """Strategy class for external SmartMeter devices."""
