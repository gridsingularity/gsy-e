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
from d3a.models.strategy.load_hours import LoadHoursStrategy


class CustomLoadStrategy(LoadHoursStrategy):

    def update_posted_bids_over_ticks(self, market):
        """
        Overwrites d3a.models.strategy.load_hours_fb.update_posted_bids
        Is called on every TICK event.
        Should be used to modify the price of the bids over the ticks for the selected market.
        In the default implementation, an increase of the energy over the ticks is implemented
        """

        pass
