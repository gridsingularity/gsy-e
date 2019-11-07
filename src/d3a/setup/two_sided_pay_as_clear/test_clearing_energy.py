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
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):

    ConstSettings.IAASettings.MARKET_TYPE = 3
    ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1
    ConstSettings.GeneralSettings.MARKET_CLEARING_FREQUENCY_PER_SLOT = 1
    ConstSettings.LoadSettings.INITIAL_BUYING_RATE = 35
    ConstSettings.LoadSettings.FINAL_BUYING_RATE = 35
    ConstSettings.StorageSettings.INITIAL_BUYING_RATE = 24.99
    ConstSettings.StorageSettings.FINAL_BUYING_RATE = 25
    ConstSettings.StorageSettings.INITIAL_SELLING_RATE = 30
    ConstSettings.StorageSettings.FINAL_SELLING_RATE = 25.01

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load1', strategy=LoadHoursStrategy(
                        avg_power_W=100, hrs_per_day=24, hrs_of_day=list(range(24)),
                        initial_buying_rate=28.8, fit_to_limit=False,
                        energy_rate_increase_per_update=0),
                         appliance=SwitchableAppliance()),
                    Area('H1 General Load2', strategy=LoadHoursStrategy(
                        avg_power_W=100, hrs_per_day=24, hrs_of_day=list(range(24)),
                        initial_buying_rate=18.8, fit_to_limit=False,
                        energy_rate_increase_per_update=0),
                         appliance=SwitchableAppliance()),
                    Area('H1 General Load3', strategy=LoadHoursStrategy(
                        avg_power_W=100, hrs_per_day=24, hrs_of_day=list(range(24)),
                        initial_buying_rate=8.8, fit_to_limit=False,
                        energy_rate_increase_per_update=0),
                         appliance=SwitchableAppliance()),
                    Area('H1 CEP1',
                         strategy=FinitePowerPlant(energy_rate=5.1, max_available_power_kW=0.1),
                         appliance=SimpleAppliance()),
                    Area('H1 CEP2',
                         strategy=FinitePowerPlant(energy_rate=15.5, max_available_power_kW=0.1),
                         appliance=SimpleAppliance()),
                    Area('H1 CEP3',
                         strategy=FinitePowerPlant(energy_rate=25.001, max_available_power_kW=0.1),
                         appliance=SimpleAppliance()),
                    Area('H1 CEP4',
                         strategy=FinitePowerPlant(energy_rate=28.001, max_available_power_kW=0.1),
                         appliance=SimpleAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
