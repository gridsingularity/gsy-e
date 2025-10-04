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
from math import isclose

from unittest.mock import patch
from pendulum import DateTime
from gsy_framework.constants_limits import (
    TIME_ZONE,
)

from gsy_e.models.strategy.ev_charger import (
    EVChargerStrategy,
    EVChargingSession,
    GridIntegrationType,
)

from .test_strategy_storage import FakeArea, area_test1, FakeMarket, auto_fixture, area_test7


@pytest.fixture()
def ev_charger_strategy(area_test1, called):
    strategy = EVChargerStrategy(
        maximum_power_rating_kW=2.01,
        initial_buying_rate=31,
        final_buying_rate=31,
        initial_selling_rate=32,
        final_selling_rate=32,
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


def test_if_ev_charger_buys_energy(ev_charger_strategy, area_test1):
    # Given
    # When
    ev_charger_strategy.event_activate()
    ev_charger_strategy.event_tick()

    # Then
    assert ev_charger_strategy.accept_offer.calls[0][0][1] == repr(FakeMarket(0).sorted_offers[0])


def test_if_ev_charger_doesnt_buy_outside_session(ev_charger_strategy, area_test1):
    # Given
    session = ev_charger_strategy.charging_sessions[0]

    # When
    outside_time = session.plug_in_time.add(hours=3)
    with patch.object(
        type(area_test1.spot_market),
        "time_slot",
        new=property(lambda _: outside_time),
    ):
        ev_charger_strategy.event_activate()
        ev_charger_strategy.event_tick()

    # Then
    assert len(ev_charger_strategy.accept_offer.calls) == 0


def test_if_ev_charger_sells_energy(ev_charger_strategy, area_test7):
    # Given
    new_session = EVChargingSession(
        DateTime.now(tz=TIME_ZONE).start_of("day"),
        duration_minutes=120,
        initial_soc_percent=99.667,
        min_soc_percent=50.0,
        battery_capacity_kWh=3.01,
    )
    ev_charger_strategy.charging_sessions[0] = new_session

    # When
    ev_charger_strategy.event_activate()
    sell_market = area_test7.spot_market
    energy_sell_dict = ev_charger_strategy.state._clamp_energy_to_sell_kWh([sell_market.time_slot])
    ev_charger_strategy.event_market_cycle()

    # Then
    assert isclose(
        ev_charger_strategy.state.offered_sell_kWh[sell_market.time_slot],
        energy_sell_dict[sell_market.time_slot],
        rel_tol=1e-03,
    )
    assert isclose(ev_charger_strategy.state.used_storage, 3.0, rel_tol=1e-03)
    assert len(ev_charger_strategy.offers.posted_in_market(sell_market.id)) > 0


def test_if_unidirectional_ev_charger_doesnt_sell_energy(ev_charger_strategy, area_test7):
    # Given
    new_session = EVChargingSession(
        DateTime.now(tz=TIME_ZONE).start_of("day"),
        duration_minutes=120,
        initial_soc_percent=99.667,
        min_soc_percent=50.0,
        battery_capacity_kWh=3.01,
    )
    ev_charger_strategy.charging_sessions[0] = new_session
    ev_charger_strategy.grid_integration = GridIntegrationType.UNIDIRECTIONAL

    # When
    ev_charger_strategy.event_activate()
    sell_market = area_test7.spot_market
    ev_charger_strategy.event_market_cycle()

    # Then
    assert ev_charger_strategy.state.offered_sell_kWh[sell_market.time_slot] == 0
    assert len(ev_charger_strategy.offers.posted_in_market(sell_market.id)) == 0
