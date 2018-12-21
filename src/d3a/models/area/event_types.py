"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


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
