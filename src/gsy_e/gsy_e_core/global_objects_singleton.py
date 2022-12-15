"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from gsy_e.gsy_e_core.user_profile_handler import ProfilesHandler
from gsy_e.gsy_e_core.global_stats import (
    ExternalConnectionGlobalStatistics, SCMExternalConnectionGlobalStatistics)


class GlobalObjects:
    """Collection of global singletons"""

    profiles_handler = ProfilesHandler()
    external_global_stats = ExternalConnectionGlobalStatistics()
    scm_external_global_stats = SCMExternalConnectionGlobalStatistics()


global_objects = GlobalObjects()
