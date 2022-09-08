"""
Copyright 2022 BC4P
This file is part of BC4P.

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
from gsy_e.models.area import Area
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_e.utils.influx_area_factory import InfluxAreaFactory
from gsy_e.gsy_e_core.util import d3a_path
import os

def get_setup(config):
    ConstSettings.GeneralSettings.RUN_IN_REALTIME = True
    factory = InfluxAreaFactory(os.path.join(d3a_path, "resources", "influx_fhaachen.cfg"), power_column="P_ges", tablename="Strom", keyname="id")
    area = Area(
        "Grid",
        [
            factory.getArea("FH Campus"),
            Area("Commercial Energy Producer",
                 strategy=CommercialStrategy(energy_rate=30)
                 )
        ],
        config=config
    )
    return area
