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

from unittest.mock import patch
from math import isclose

import pytest
from pendulum import DateTime
from gsy_framework.constants_limits import TIME_ZONE
from gsy_framework.enums import EVChargerStatus

from gsy_e.models.strategy.ev_charger import (
    EVChargerStrategy,
    EVChargingSession,
    GridIntegrationType,
)
from gsy_e.models.strategy.state.storage_state import StorageLosses


# flake8: noqa
from .test_strategy_storage import (
    FakeArea,
    area_test1,
    FakeMarket,
    auto_fixture,
    area_test7,
)  # pylint: disable=line-too-long


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
    ev_charger_strategy.grid_integration = GridIntegrationType.BIDIRECTIONAL

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
    assert isclose(ev_charger_strategy.state.ev_sessions_manager.used_storage, 3.0, rel_tol=1e-03)
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


def test_if_preferred_charging_power_overrides_bought_energy(ev_charger_strategy, area_test1):
    # Given
    preferred_power_kW = 1.5
    strategy = EVChargerStrategy(
        maximum_power_rating_kW=ev_charger_strategy.maximum_power_rating_kW,
        initial_buying_rate=ev_charger_strategy.bid_update.initial_rate_profile_buffer.profile,
        final_buying_rate=ev_charger_strategy.bid_update.final_rate_profile_buffer.profile,
        initial_selling_rate=ev_charger_strategy.offer_update.initial_rate_profile_buffer.profile,
        final_selling_rate=ev_charger_strategy.offer_update.final_rate_profile_buffer.profile,
        charging_sessions=ev_charger_strategy.charging_sessions,
        preferred_charging_power=preferred_power_kW,
    )
    strategy.owner = area_test1
    strategy.area = area_test1

    # When
    strategy.event_activate()
    time_slot = area_test1.spot_market.time_slot

    # Then
    slot_length_hours = area_test1.config.slot_length.total_hours()
    expected_energy_kWh = preferred_power_kW * slot_length_hours
    actual_energy_kWh = strategy.state.get_available_energy_to_buy_kWh(time_slot)
    assert isclose(actual_energy_kWh, expected_energy_kWh, rel_tol=1e-03)


def test_get_aggregate_energy_return_correct_values():
    # Given
    now = DateTime.now(tz=TIME_ZONE).start_of("day")
    session1 = EVChargingSession(
        plug_in_time=now,
        duration_minutes=120,
        initial_soc_percent=20.0,
        min_soc_percent=10.0,
        battery_capacity_kWh=50.0,
    )
    session2 = EVChargingSession(
        plug_in_time=now,
        duration_minutes=120,
        initial_soc_percent=50.0,
        min_soc_percent=20.0,
        battery_capacity_kWh=75.0,
    )
    session3 = EVChargingSession(
        plug_in_time=now,
        duration_minutes=120,
        initial_soc_percent=80.0,
        min_soc_percent=30.0,
        battery_capacity_kWh=100.0,
    )

    strategy = EVChargerStrategy(
        maximum_power_rating_kW=10.0,
        charging_sessions=[session1, session2, session3],
    )

    # When
    total_energy_to_buy = strategy.state.ev_sessions_manager.get_aggregate_energy_to_buy_kWh(now)
    total_energy_to_sell = strategy.state.ev_sessions_manager.get_aggregate_energy_to_sell_kWh(now)

    # Then - Should aggregate remaining capacity from all 3 sessions (not limited by power yet)
    # session1: 50 - (50 * 0.2) = 50 - 10 = 40 kWh remaining capacity
    # session2: 75 - (75 * 0.5) = 75 - 37.5 = 37.5 kWh remaining capacity
    # session3: 100 - (100 * 0.8) = 100 - 80 = 20 kWh remaining capacity
    expected_buy = 40.0 + 37.5 + 20.0  # Total remaining capacity across all sessions
    assert isclose(total_energy_to_buy, expected_buy, rel_tol=1e-03)

    # For selling - aggregate energy above min_soc from all sessions (not limited by power yet)
    # session1: (20-10)% of 50 = 5 kWh available
    # session2: (50-20)% of 75 = 22.5 kWh available
    # session3: (80-30)% of 100 = 50 kWh available
    expected_sell = 5.0 + 22.5 + 50.0  # Total available energy above min_soc
    assert isclose(total_energy_to_sell, expected_sell, rel_tol=1e-03)


def test_energy_distribution_prioritizes_low_soc(area_test1):
    # Given - Two EVs with different SOCs
    now = DateTime.now(tz=TIME_ZONE).start_of("day")
    session_low_soc = EVChargingSession(
        plug_in_time=now,
        duration_minutes=120,
        initial_soc_percent=20.0,
        min_soc_percent=10.0,
        battery_capacity_kWh=100.0,
    )
    session_high_soc = EVChargingSession(
        plug_in_time=now,
        duration_minutes=120,
        initial_soc_percent=80.0,
        min_soc_percent=10.0,
        battery_capacity_kWh=100.0,
    )

    strategy = EVChargerStrategy(
        maximum_power_rating_kW=10.0,
        charging_sessions=[session_low_soc, session_high_soc],
        losses=StorageLosses(charging_loss_percent=0.1, discharging_loss_percent=0.1),
    )
    strategy.owner = area_test1
    strategy.area = area_test1

    # When
    strategy.event_activate()
    manager = strategy.state.ev_sessions_manager
    sessions = manager.sessions
    initial_low_soc = sessions[0].current_energy_kWh
    initial_high_soc = sessions[1].current_energy_kWh
    distribution = manager.distribute_bought_energy(now, 10.0)

    # Then - Low SOC session should get more energy
    # Effective energy after 10% loss: 9 kWh
    # Weights: low_soc = 100-20 = 80, high_soc = 100-80 = 20
    # Total weight = 100
    # low_soc gets: 9 * (80/100) = 7.2 kWh
    # high_soc gets: 9 * (20/100) = 1.8 kWh
    assert isclose(distribution[sessions[0].session_id], 7.2, rel_tol=1e-03)
    assert isclose(distribution[sessions[1].session_id], 1.8, rel_tol=1e-03)

    # Verify sessions received the distributed energy
    assert isclose(sessions[0].current_energy_kWh - initial_low_soc, 7.2, rel_tol=1e-03)
    assert isclose(sessions[1].current_energy_kWh - initial_high_soc, 1.8, rel_tol=1e-03)


def test_energy_distribution_for_selling_prioritizes_high_soc(area_test1):
    # Given
    now = DateTime.now(tz=TIME_ZONE).start_of("day")
    session_low_soc = EVChargingSession(
        plug_in_time=now,
        duration_minutes=120,
        initial_soc_percent=30.0,
        min_soc_percent=20.0,
        battery_capacity_kWh=100.0,
    )
    session_high_soc = EVChargingSession(
        plug_in_time=now,
        duration_minutes=120,
        initial_soc_percent=90.0,
        min_soc_percent=20.0,
        battery_capacity_kWh=100.0,
    )

    strategy = EVChargerStrategy(
        maximum_power_rating_kW=10.0,
        charging_sessions=[session_low_soc, session_high_soc],
        losses=StorageLosses(charging_loss_percent=0.1, discharging_loss_percent=0.1),
    )
    strategy.owner = area_test1
    strategy.area = area_test1

    # When
    strategy.event_activate()
    manager = strategy.state.ev_sessions_manager
    sessions = manager.sessions
    initial_low_soc = sessions[0].current_energy_kWh
    initial_high_soc = sessions[1].current_energy_kWh
    distribution = manager.distribute_sold_energy(now, 10.0)

    # Then - High SOC session should contribute more
    # Weights: low_soc = 30-20 = 10, high_soc = 90-20 = 70
    # low_soc contributes: 10 * (10/80) = 1.25 kWh (removed from session)
    # high_soc contributes: 10 * (70/80) = 8.75 kWh (removed from session)
    # After 10% discharging loss, distribution shows what goes to market:
    assert isclose(distribution[sessions[0].session_id], 1.25 * 0.9, rel_tol=1e-03)
    assert isclose(distribution[sessions[1].session_id], 8.75 * 0.9, rel_tol=1e-03)

    # Verify sessions lost the correct amount (before loss adjustment)
    assert isclose(initial_low_soc - sessions[0].current_energy_kWh, 1.25, rel_tol=1e-03)
    assert isclose(initial_high_soc - sessions[1].current_energy_kWh, 8.75, rel_tol=1e-03)


def test_non_overlapping_sessions(area_test1):
    # Given
    now = DateTime.now(tz=TIME_ZONE).start_of("day")
    session1 = EVChargingSession(
        plug_in_time=now,
        duration_minutes=60,
        initial_soc_percent=20.0,
        battery_capacity_kWh=50.0,
    )
    session2 = EVChargingSession(
        plug_in_time=now.add(hours=2),
        duration_minutes=60,
        initial_soc_percent=30.0,
        battery_capacity_kWh=60.0,
    )

    strategy = EVChargerStrategy(
        maximum_power_rating_kW=10.0,
        charging_sessions=[session1, session2],
    )
    strategy.owner = area_test1
    strategy.area = area_test1

    # When/Then
    strategy.event_activate()
    manager = strategy.state.ev_sessions_manager
    sessions = manager.sessions

    active_at_now = manager.get_active_sessions(now)
    assert len(active_at_now) == 1
    assert active_at_now[0] == sessions[0]

    active_2h_later = manager.get_active_sessions(now.add(hours=2))
    assert len(active_2h_later) == 1
    assert active_2h_later[0] == sessions[1]

    active_5h_later = manager.get_active_sessions(now.add(hours=5))
    assert len(active_5h_later) == 0


def test_ev_charger_state_reports_min_max_soc(area_test1):
    # Given
    now = DateTime.now(tz=TIME_ZONE).start_of("day")
    sessions = [
        EVChargingSession(
            plug_in_time=now,
            duration_minutes=120,
            initial_soc_percent=25.0,
            battery_capacity_kWh=50.0,
        ),
        EVChargingSession(
            plug_in_time=now,
            duration_minutes=120,
            initial_soc_percent=75.0,
            battery_capacity_kWh=60.0,
        ),
        EVChargingSession(
            plug_in_time=now,
            duration_minutes=120,
            initial_soc_percent=50.0,
            battery_capacity_kWh=70.0,
        ),
    ]

    strategy = EVChargerStrategy(
        maximum_power_rating_kW=10.0,
        charging_sessions=sessions,
    )
    strategy.owner = area_test1
    strategy.area = area_test1

    # When
    strategy.event_activate()
    results = strategy.state.get_results_dict(now)

    # Then
    assert results["status"] == EVChargerStatus.ACTIVE
    assert results["active_sessions_count"] == 3
    assert isclose(results["min_soc_%"], 25.0, rel_tol=1e-03)
    assert isclose(results["max_soc_%"], 75.0, rel_tol=1e-03)
    assert len(results["sessions"]) == 3


def test_used_storage_aggregates_all_sessions(area_test1):
    # Given
    now = DateTime.now(tz=TIME_ZONE).start_of("day")
    sessions = [
        EVChargingSession(
            plug_in_time=now,
            duration_minutes=120,
            initial_soc_percent=50.0,
            battery_capacity_kWh=50.0,
        ),
        EVChargingSession(
            plug_in_time=now,
            duration_minutes=120,
            initial_soc_percent=60.0,
            battery_capacity_kWh=100.0,
        ),
    ]

    strategy = EVChargerStrategy(
        maximum_power_rating_kW=10.0,
        charging_sessions=sessions,
    )
    strategy.owner = area_test1
    strategy.area = area_test1

    # When
    strategy.event_activate()

    # Then
    # session1: 50% of 50 kWh = 25 kWh
    # session2: 60% of 100 kWh = 60 kWh
    expected_total = 25.0 + 60.0
    assert isclose(strategy.state.ev_sessions_manager.used_storage, expected_total, rel_tol=1e-03)


def test_charging_efficiency_applies_losses(area_test1):
    # Given
    now = DateTime.now(tz=TIME_ZONE).start_of("day")
    charging_efficiency = 0.95  # 5% loss
    session = EVChargingSession(
        plug_in_time=now,
        duration_minutes=120,
        initial_soc_percent=20.0,
        battery_capacity_kWh=100.0,
    )

    strategy = EVChargerStrategy(
        maximum_power_rating_kW=10.0,
        charging_sessions=[session],
        losses=StorageLosses(
            charging_loss_percent=1.0 - charging_efficiency,
            discharging_loss_percent=1.0 - charging_efficiency,
        ),
    )
    strategy.owner = area_test1
    strategy.area = area_test1

    # When
    strategy.event_activate()
    manager = strategy.state.ev_sessions_manager
    sessions = manager.sessions
    distribution = manager.distribute_bought_energy(now, 10.0)

    # Then
    # session receives 10 * 0.95 = 9.5 kWh
    assert isclose(distribution[sessions[0].session_id], 9.5, rel_tol=1e-03)
    expected_energy = 20.0 + 9.5  # started at 20 kWh
    assert isclose(sessions[0].current_energy_kWh, expected_energy, rel_tol=1e-03)
