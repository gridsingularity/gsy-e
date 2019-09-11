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
import json
import os
import pendulum


def export_default_settings_to_json_file():
    from d3a.constants import DATE_FORMAT
    from d3a.d3a_core.util import d3a_path
    from d3a.d3a_core.util import constsettings_to_dict
    from d3a_interface.constants_limits import GlobalConfig

    base_settings = {
            "sim_duration": f"{GlobalConfig.DURATION_D*24}h",
            "slot_length": f"{GlobalConfig.SLOT_LENGTH_M}m",
            "tick_length": f"{GlobalConfig.TICK_LENGTH_S}s",
            "market_count": GlobalConfig.MARKET_COUNT,
            "cloud_coverage": GlobalConfig.CLOUD_COVERAGE,
            "iaa_fee": GlobalConfig.IAA_FEE,
            "start_date": pendulum.instance(GlobalConfig.start_date).format(DATE_FORMAT),
    }
    all_settings = {"basic_settings": base_settings, "advanced_settings": constsettings_to_dict()}
    settings_filename = os.path.join(d3a_path, "setup", "d3a-settings.json")
    with open(settings_filename, "w") as settings_file:
        settings_file.write(json.dumps(all_settings, indent=2))
