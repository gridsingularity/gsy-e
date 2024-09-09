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
from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_e.models.area.throughput_parameters import ThroughputParameters


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    area = Area("Grid", children=[
        Area("Community", children=[
            Area("House 1", children=[
                Area("H1 Seller", strategy=FinitePowerPlant(energy_rate=5,
                                                            max_available_power_kW=0.5)
                     ),
                Area("H1 Buyer", strategy=LoadHoursStrategy(avg_power_W=1000,
                                                            hrs_of_day=list(range(24)),
                                                            fit_to_limit=False,
                                                            initial_buying_rate=4,
                                                            energy_rate_increase_per_update=0)
                     )],
                 throughput=ThroughputParameters(import_capacity_kVA=1, export_capacity_kVA=1,
                 baseline_peak_energy_import_kWh=1, baseline_peak_energy_export_kWh=1)
                 ),
            Area("Community Load", strategy=LoadHoursStrategy(avg_power_W=500,
                                                              hrs_of_day=list(range(24)),
                                                              fit_to_limit=False,
                                                              initial_buying_rate=6,
                                                              energy_rate_increase_per_update=0)
                 )]),
        Area("Market Maker", strategy=MarketMakerStrategy(energy_rate=3),
             )],
                config=config)
    return area
