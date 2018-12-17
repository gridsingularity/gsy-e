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
from logging import getLogger

from cached_property import cached_property

from d3a.d3a_core.util import TaggedLogWrapper

log = getLogger(__name__)


class AreaBehaviorBase:
    """Base class used by area behaviour defining classes (`BaseStrategy`, `BaseAppliance`)"""
    def __init__(self):
        # `area` is the area we trade in
        self.area = None  # type: ".area.Area"
        # `owner` is the area of which we are the strategy, usually a child of `area`
        self.owner = None  # type: ".area.Area"

    @cached_property
    def _log(self):
        return TaggedLogWrapper(log, "{s.owner.name}:{s.__class__.__name__}".format(s=self))

    @property
    def log(self):
        if not self.owner:
            log.warning("Logging without area in %s, using default logger",
                        self.__class__.__name__)
            return log
        return self._log
