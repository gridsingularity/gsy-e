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

import pytest

from pendulum import now, DateTime
from gsy_framework.constants_limits import (
    TIME_ZONE,
)

from gsy_e.models.strategy.ev_charger import EVChargerStrategy, EVChargingSession

from .test_strategy_storage import FakeArea, area_test1, FakeMarket, auto_fixture


@pytest.fixture()
def ev_charger_strategy(area_test1, called):
    strategy = EVChargerStrategy(
        maximum_power_rating_kW=2.01,
        initial_buying_rate=23.6,
        final_buying_rate=23.6,
        initial_selling_rate=23.7,
        final_selling_rate=23.7,
        charging_sessions=[
            EVChargingSession(
                DateTime.now(tz=TIME_ZONE).start_of("day"),
                duration_minutes=120,
            )
        ],
    )
    strategy.owner = area_test1
    strategy.area = area_test1
    strategy.accept_offer = called
    return strategy


def test_if_ev_charger_buys_cheap_energy(ev_charger_strategy, area_test1):
    ev_charger_strategy.event_activate()
    ev_charger_strategy.event_tick()
    for _ in range(5):
        area_test1.current_tick += 310
        ev_charger_strategy.event_tick()
    assert ev_charger_strategy.accept_offer.calls[0][0][1] == repr(FakeMarket(0).sorted_offers[0])
