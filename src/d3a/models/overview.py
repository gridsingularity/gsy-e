import logging
import requests

from d3a.models.events import AreaEvent


class Overview:
    """
    Send regular updates to d3a-web: Json object with overall
    status of the running simulation.
    """
    def __init__(self, area, url, ticks_per_update=None):
        self.area = area
        self.url = url
        self.ticks_per_update = ticks_per_update or area.config.ticks_per_slot
        self.log = logging.getLogger(__name__)
        area.add_listener(self)

    def event_listener(self, event_type, **kwargs):
        if event_type == AreaEvent.TICK:
            if self.area.current_tick % self.ticks_per_update == 0 and self.area.current_tick > 0:
                try:
                    requests.post(self.url, json=self.current_data())
                except Exception as ex:
                    self.log.critical("Could not send simulation update: %s" % str(ex))

    def current_data(self):
            return {'todo': 'post data'}
