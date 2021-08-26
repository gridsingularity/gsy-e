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
from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy

from tests.strategies.external.utils import (
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture)


@pytest.fixture
def ext_load_fixture():
    return create_areas_markets_for_strategy_fixture(LoadHoursExternalStrategy(100))


class TestPVForecastExternalStrategy:

    def test_bid_succeeds(self, ext_load_fixture):
        arguments = {"price": 1, "energy": 2}
        check_external_command_endpoint_with_correct_payload_succeeds(ext_load_fixture,
                                                                      "bid", arguments)

    def test_list_bids_succeeds(self, ext_load_fixture):
        check_external_command_endpoint_with_correct_payload_succeeds(ext_load_fixture,
                                                                      "list_bids", {})

    def test_delete_bid_succeeds(self, ext_load_fixture):
        check_external_command_endpoint_with_correct_payload_succeeds(ext_load_fixture,
                                                                      "delete_bid", {})