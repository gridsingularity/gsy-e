

class IntervalAreaEvent:
    def __init__(self, disconnect_start, disconnect_end):
        self.disconnect_start = disconnect_start
        self.disconnect_end = disconnect_end
        self._active = True

    @property
    def active(self):
        return self._active

    def tick(self, current_time):
        self._active = not self.disconnect_start <= current_time.hour < self.disconnect_end


class DisableIntervalAreaEvent(IntervalAreaEvent):
    pass


class DisconnectIntervalAreaEvent(IntervalAreaEvent):
    pass


class SimpleEvent:
    def __init__(self, event_time):
        self.event_time = event_time


class DisconnectAreaEvent(SimpleEvent):
    pass


class ConnectAreaEvent(SimpleEvent):
    pass


class DisableAreaEvent(SimpleEvent):
    pass


class EnableAreaEvent(SimpleEvent):
    pass
