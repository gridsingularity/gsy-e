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
from d3a.is_installed import is_installed

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
VERSION = "1.0.0a0"

if is_installed("d3a_interface"):
    from d3a_interface.constants_limits import TimeConstants
    TIME_FORMAT = TimeConstants.TIME_FORMAT
    DATE_FORMAT = TimeConstants.DATE_FORMAT
    DATE_TIME_FORMAT = TimeConstants.DATE_TIME_FORMAT
    DATE_TIME_UI_FORMAT = TimeConstants.DATE_TIME_UI_FORMAT
    TIME_ZONE = TimeConstants.TIME_ZONE
else:
    TIME_FORMAT = "HH:mm"
    DATE_FORMAT = "YYYY-MM-DD"
    DATE_TIME_FORMAT = f"{DATE_FORMAT}T{TIME_FORMAT}"
    DATE_TIME_UI_FORMAT = "MMMM DD YYYY, HH:mm [h]"
    TIME_ZONE = "UTC"

DEFAULT_PRECISION = 8
FLOATING_POINT_TOLERANCE = 0.000001
