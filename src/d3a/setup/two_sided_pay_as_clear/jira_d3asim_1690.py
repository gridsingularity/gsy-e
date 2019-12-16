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
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 3
    ConstSettings.GeneralSettings.MARKET_CLEARING_FREQUENCY_PER_SLOT = 1
    ConstSettings.GeneralSettings.SUPPLY_DEMAND_PLOTS = False

    area = Area(
        'GRID',
        [
            Area(
                'LEM',
                [
                    Area(
                        'House 1',
                        [
                            Area('Load H1', strategy=LoadHoursStrategy(
                                avg_power_W=200, hrs_per_day=24, hrs_of_day=range(24),
                                final_buying_rate=30, initial_buying_rate=15,
                                fit_to_limit=True, update_interval=5),
                                 appliance=SwitchableAppliance()),
                            Area('H1 PV', strategy=PVStrategy(
                                panel_count=1, initial_selling_rate=13,
                                fit_to_limit=False,
                                energy_rate_decrease_per_update=1,
                                update_interval=5),
                                 appliance=PVAppliance()),
                        ], transfer_fee_pct=0, transfer_fee_const=0,
                    ),
                    Area(
                        'House 2',
                        [
                            Area('Load H2', strategy=LoadHoursStrategy(
                                avg_power_W=200, hrs_per_day=24, hrs_of_day=range(24),
                                final_buying_rate=30, initial_buying_rate=18,
                                fit_to_limit=True, update_interval=5),
                                 appliance=SwitchableAppliance()),
                            Area('H2 PV', strategy=PVStrategy(
                                panel_count=1, initial_selling_rate=24,
                                fit_to_limit=False,
                                energy_rate_decrease_per_update=1,
                                update_interval=5),
                                 appliance=PVAppliance()),
                            ], transfer_fee_pct=0, transfer_fee_const=0,
                    ),
                    Area(
                        'House 3',
                        [
                            Area('Load H3', strategy=LoadHoursStrategy(
                                avg_power_W=200, hrs_per_day=24, hrs_of_day=range(24),
                                final_buying_rate=30, initial_buying_rate=16,
                                update_interval=5),
                                 appliance=SwitchableAppliance()),
                        ], transfer_fee_pct=0, transfer_fee_const=0,
                    ),
                    Area(
                        'House 4',
                        [
                            Area('Load H4', strategy=LoadHoursStrategy(
                                avg_power_W=200, hrs_per_day=24, hrs_of_day=range(24),
                                final_buying_rate=30, initial_buying_rate=15,
                                update_interval=5),
                                 appliance=SwitchableAppliance()),
                        ], transfer_fee_pct=0, transfer_fee_const=0,
                    ),
                ],
            ),
            Area('Infinite Bus', strategy=InfiniteBusStrategy(
                energy_buy_rate=12, energy_sell_rate=30),
                 appliance=SimpleAppliance()),
        ],
        config=config

    )
    return area
