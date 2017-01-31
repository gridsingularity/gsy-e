from d3a.models.base import AreaBehaviorBase
from d3a.models.events import EventMixin, TriggerMixin


class BaseAppliance(TriggerMixin, EventMixin, AreaBehaviorBase):
    pass
