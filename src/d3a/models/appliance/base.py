from d3a.models.base import AreaBehaviorBase
from d3a.events.event_structures import TriggerMixin
from d3a.events import EventMixin


class BaseAppliance(TriggerMixin, EventMixin, AreaBehaviorBase):
    pass
