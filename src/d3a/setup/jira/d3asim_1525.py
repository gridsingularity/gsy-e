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
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.d3a_core.util import d3a_path
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a_interface.constants_limits import ConstSettings
import os

"""
This setup file reenacts a case where the assert "Accepted bids were not enough to satisfy the
offer, should never reach this point."
in TwoSidedPayAsClearEngine._exhaust_offer_for_selected_bids is called before fixing the bug
as part of D3ASIM-1525.
"""

load_profile_path = os.path.join(d3a_path, 'resources', 'SAM_MF2_Summer.csv')

house1_pv_production = {
    0: 0,
    9: 100,
    10: 460,
    11: 700,
    12: 2200,
    13: 4700,
    14: 4500,
    15: 4300,
    16: 6000,
    17: 1700,
    18: 0
}

house2_load_dict = {
    0: 20,
    6: 1000,
    10: 200,
    22: 100,
}
house3_load_dict = {
    0: 30,
    6: 600,
    10: 400,
    23: 100,
}


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 3
    area = Area(
            'Grid',
            [
                    Area(
                            'House 1',
                            [
                                    Area('H1 PV', strategy=PVUserProfileStrategy(
                                                power_profile=house1_pv_production),
                                         appliance=PVAppliance()),
                                    Area('H1 General Load', strategy=DefinedLoadStrategy(
                                        daily_load_profile=load_profile_path,
                                        final_buying_rate=28),
                                         appliance=SwitchableAppliance()),
                             ]),
                    Area(
                            'House 2',
                            [
                                    Area('H2 PV', strategy=PVStrategy(30),
                                         appliance=PVAppliance()),
                                    Area('H2 General Load',
                                         strategy=DefinedLoadStrategy(
                                             daily_load_profile=house2_load_dict),
                                         appliance=SwitchableAppliance()),
                             ]),
                    Area(
                            'House 3',
                            [
                                    Area('H3 General Load', strategy=DefinedLoadStrategy(
                                        daily_load_profile=house3_load_dict,
                                        final_buying_rate=25),
                                         appliance=SwitchableAppliance()),
                            ]),
                    Area(
                            'House 4',
                            [
                                    Area('H4 General Load',
                                         strategy=DefinedLoadStrategy(
                                             daily_load_profile=load_profile_path,
                                             final_buying_rate=24),
                                         appliance=SwitchableAppliance()),
                            ]),
                    Area('Infinite Power Plant', strategy=CommercialStrategy(energy_rate=30),
                         appliance=SimpleAppliance()),
                            ],
            config=config
        )
    return area
