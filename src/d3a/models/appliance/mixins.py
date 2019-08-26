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
from d3a.events.event_structures import Trigger


class SwitchableMixin:
    available_triggers = [
        Trigger('on', state_getter=lambda s: s.is_on,
                help="Turn appliance on. Starts consuming energy."),
        Trigger('off', state_getter=lambda s: not s.is_on,
                help="Turn appliance off. Stops consuming energy.")
    ]

    parameters = ('initially_on',)

    def __init__(self, *args, initially_on=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_on = initially_on
        self.initially_on = initially_on

    def trigger_on(self):
        self.is_on = True
        self.log.info("Turning on")

    def trigger_off(self):
        self.is_on = False
        self.log.info("Turning off")
