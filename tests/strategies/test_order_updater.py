from math import isclose

import pytest
from gsy_framework.constants_limits import GlobalConfig
from pendulum import duration, datetime

from gsy_e.models.market import MarketSlotParams
from gsy_e.models.strategy.order_updater import OrderUpdater, OrderUpdaterParameters

UPDATE_INTERVAL = duration(minutes=5)


@pytest.fixture(name="order_updater_fixture")
def fixture_order_updater():
    initial_tick_length = GlobalConfig.tick_length
    GlobalConfig.tick_length = duration(seconds=5)
    opening_time = datetime(year=2022, month=1, day=1, hour=12, minute=30)

    updater = OrderUpdater(
        OrderUpdaterParameters(UPDATE_INTERVAL, initial_rate=30, final_rate=70),
        MarketSlotParams(
            opening_time=opening_time,
            closing_time=opening_time + duration(minutes=30),
            delivery_start_time=opening_time + duration(hours=2),
            delivery_end_time=opening_time + duration(hours=3),
        ),
    )

    yield opening_time, updater
    GlobalConfig.tick_length = initial_tick_length


class TestOrderUpdater:

    @staticmethod
    def test_order_updater_calculates_update_times_correctly(order_updater_fixture):
        opening_time = order_updater_fixture[0]
        updater = order_updater_fixture[1]
        # Returns False before the market open time
        assert not updater.is_time_for_update(opening_time - duration(minutes=1))
        # Returns False at the market close time
        assert not updater.is_time_for_update(opening_time + duration(minutes=30))

        current_time = opening_time
        while current_time < opening_time + duration(minutes=30) - duration(seconds=5):
            assert updater.is_time_for_update(current_time) is True
            current_time += duration(minutes=5)

    @staticmethod
    def test_get_energy_rate(order_updater_fixture):
        opening_time = order_updater_fixture[0]
        updater = order_updater_fixture[1]
        rate_range = 70 - 30
        update_time = duration(minutes=30)
        closing_time = opening_time + update_time
        current_time = opening_time
        while current_time < closing_time:
            expected_rate = 30 + rate_range * (
                (current_time - opening_time) / (update_time - UPDATE_INTERVAL)
            )
            assert isclose(updater.get_energy_rate(current_time), expected_rate, abs_tol=0.0001)
            current_time += duration(minutes=5)

        assert isclose(updater.get_energy_rate(closing_time - UPDATE_INTERVAL), 70, abs_tol=0.0001)
