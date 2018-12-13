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


class StrategyEvents(SimpleEvent):
    def __init__(self, event_time, params):
        super().__init__(event_time)
        self.params = params
        self._triggered = False

    def tick(self, current_time, strategy):
        if current_time.hour == self.event_time and not self._triggered:
            strategy.area_reconfigure_event(**self.params)
            self._triggered = True
