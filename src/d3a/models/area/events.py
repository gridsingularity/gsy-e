from d3a.models.area.event_types import EnableAreaEvent, DisableAreaEvent, ConnectAreaEvent, \
    DisconnectAreaEvent, DisableIntervalAreaEvent, DisconnectIntervalAreaEvent, StrategyEvents


class IndividualEvents:
    def __init__(self, event_list, trigger_type):
        self.event_list = event_list
        self.trigger_type = trigger_type
        self._active = True

    def tick(self, current_time):
        event_list = sorted(self.event_list, key=lambda e: e.event_time)
        past_events = list(filter(lambda e: e.event_time <= current_time.hour, event_list))
        self._active = len(past_events) == 0 or type(past_events[-1]) == self.trigger_type

    @property
    def active(self):
        return self._active


class IndividualEnableDisableEvents(IndividualEvents):
    def __init__(self, event_list):
        assert all(type(e) in [EnableAreaEvent, DisableAreaEvent] for e in event_list)
        super().__init__(event_list, EnableAreaEvent)


class IndividualConnectDisconnectEvents(IndividualEvents):
    def __init__(self, event_list):
        assert all(type(e) in [ConnectAreaEvent, DisconnectAreaEvent] for e in event_list)
        super().__init__(event_list, ConnectAreaEvent)


class EnableDisableEvents:
    def __init__(self, isolated_events, interval_events):
        self.isolated_ev = IndividualEnableDisableEvents(isolated_events)
        assert all(type(e) is DisableIntervalAreaEvent for e in interval_events)
        self.interval_ev = interval_events

    def update_events(self, current_time):
        self.isolated_ev.tick(current_time)
        for e in self.interval_ev:
            e.tick(current_time)

    @property
    def enabled(self):
        return self.isolated_ev.active and all(e.active for e in self.interval_ev)


class ConnectDisconnectEvents:
    def __init__(self, isolated_events, interval_events):
        self.isolated_ev = IndividualConnectDisconnectEvents(isolated_events)
        assert all(type(e) is DisconnectIntervalAreaEvent for e in interval_events)
        self.interval_ev = interval_events

    def update_events(self, current_time):
        self.isolated_ev.tick(current_time)
        for e in self.interval_ev:
            e.tick(current_time)

    @property
    def connected(self):
        return self.isolated_ev.active and all(e.active for e in self.interval_ev)


class Events:
    def __init__(self, event_list, strategy):
        self.strategy = strategy
        self.enable_disable_events = EnableDisableEvents(
            [e for e in event_list if type(e) in [DisableAreaEvent, EnableAreaEvent]],
            [e for e in event_list if type(e) is DisableIntervalAreaEvent],
        )

        self.connect_disconnect_events = ConnectDisconnectEvents(
            [e for e in event_list if type(e) in [ConnectAreaEvent, DisconnectAreaEvent]],
            [e for e in event_list if type(e) is DisconnectIntervalAreaEvent],
        )

        self.strategy_events = [e for e in event_list if type(e) == StrategyEvents]

    def update_events(self, current_time, strategy=None):
        self.enable_disable_events.update_events(current_time)
        self.connect_disconnect_events.update_events(current_time)
        for ev in self.strategy_events:
            ev.tick(current_time, self.strategy)

    @property
    def is_enabled(self):
        return self.enable_disable_events.enabled

    @property
    def is_connected(self):
        return self.connect_disconnect_events.connected
