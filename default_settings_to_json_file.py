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


def export_default_settings_to_json_file():
    from d3a.d3a_core.util import d3a_path
    from d3a.d3a_core.util import constsettings_to_dict

    base_settings_str = '{ \n "basic_settings": { \n   "sim_duration": "24h", \n   ' \
                        '"slot_length": "60m", \n   "tick_length": "60s", \n   ' \
                        '"market_count": 1, \n   "cloud_coverage": 0, \n   ' \
                        '"iaa_fee": 1, \n  "start_date": "2019-01-01"\n },'
    constsettings_str = json.dumps({"advanced_settings": constsettings_to_dict()}, indent=2)
    settings_filename = os.path.join(d3a_path, "setup", "d3a-settings.json")
    with open(settings_filename, "w") as settings_file:
        settings_file.write(base_settings_str)
        settings_file.write(constsettings_str[1::])  # remove leading '{'
