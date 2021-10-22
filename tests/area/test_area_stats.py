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

import pytest
from d3a_interface.constants_limits import ConstSettings

from d3a.models.area import Area
from d3a.models.market.two_sided import TwoSidedMarket
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy


class FakeArea(Area):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def current_market(self):
        return TwoSidedMarket(time_slot=self.now)


class TestAreaStats:

    @staticmethod
    @pytest.fixture
    def area_fixture():
        pv_area = FakeArea(name="pv_area", strategy=PVStrategy())
        pv_area.strategy.state._forecast_measurement_deviation_kWh[pv_area.now] = 10.0
        load_area = FakeArea(name="load_area", strategy=LoadHoursStrategy(avg_power_W=100))
        load_area.strategy.state._forecast_measurement_deviation_kWh[pv_area.now] = 5
        area = FakeArea(name="parent_area", children=[pv_area, load_area])

        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = True

        yield area

        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = False

    @staticmethod
    def test_energy_deviance_for_dso(area_fixture):
        for child in area_fixture.children:
            child.stats.calculate_energy_deviances()
        area_fixture.stats.calculate_energy_deviances()
        actual_total_energy_deviance_kWh = area_fixture.stats.total_energy_deviance_kWh

        expected_total_energy_deviance_kWh = {area_fixture.now: {
            str(area_fixture.children[0].uuid):
                area_fixture.children[0].strategy.state._forecast_measurement_deviation_kWh[
                    area_fixture.now],
            str(area_fixture.children[1].uuid):
                area_fixture.children[1].strategy.state._forecast_measurement_deviation_kWh[
                    area_fixture.now]
            }
        }
        assert actual_total_energy_deviance_kWh == expected_total_energy_deviance_kWh
