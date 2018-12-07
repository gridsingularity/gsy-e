

class DisconnectIntervalAreaEvent:
    def __init__(self, disconnect_start, disconnect_end):
        self.disconnect_start = disconnect_start
        self.disconnect_end = disconnect_end
        self._connected = True

    @property
    def connected(self):
        return self._connected

    def tick(self, current_time):
        self._connected = not self.disconnect_start <= current_time.hour <= self.disconnect_end


class DeviceDisconnectIntervalEvent(DisconnectIntervalAreaEvent):
    pass


class SimpleEvent:
    def __init__(self, event_time):
        self.event_time = event_time


class DisconnectAreaEvent(SimpleEvent):
    pass


class ConnectAreaEvent(SimpleEvent):
    pass


class IndividualConnectEvents:
    def __init__(self, event_list):
        self.event_list = event_list
        self._connected = True

    def tick(self, current_time):
        event_list = sorted(self.event_list, key=lambda e: e.event_time)
        past_events = list(filter(lambda e: e.event_time <= current_time.hour, event_list))
        self._connected = len(past_events) == 0 or type(past_events[-1]) == ConnectAreaEvent

    @property
    def connected(self):
        return self._connected


class Events:
    def __init__(self, event_list):
        self.independent_events = [e for e in event_list
                                   if type(e) in [DisconnectIntervalAreaEvent,
                                                  DeviceDisconnectIntervalEvent]]
        self.correlating_events = [e for e in event_list
                                   if type(e) in [ConnectAreaEvent, DisconnectAreaEvent]]
        self.connect_events = IndividualConnectEvents(self.correlating_events)

    def update_events(self, current_time):
        self.connect_events.tick(current_time)
        for e in self.independent_events:
            e.tick(current_time)

    @property
    def is_connected(self):
        return all(e.connected for e in self.independent_events
                   if type(e) == DisconnectIntervalAreaEvent) and \
            self.connect_events.connected

    @property
    def is_device_operational(self):
        return all(not e.is_disconnected for e in self.independent_events
                   if type(e) == DeviceDisconnectIntervalEvent)
