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
import pendulum
import uuid
import pathlib
import os
from pendulum import DateTime, duration, today, datetime
from typing import Dict  # NOQA
from uuid import uuid4

from d3a.d3a_core.util import d3a_path, change_global_config
from d3a.constants import TIME_ZONE, TIME_FORMAT, CN_PROFILE_EXPANSION_DAYS, IS_CANARY_NETWORK
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market.market_structures import Offer, Trade
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.exceptions import D3ADeviceException
from d3a.d3a_core.util import generate_market_slot_list


def setup_function():
    change_global_config(**DEFAULT_CONFIG.__dict__)


ENERGY_FORECAST = {}  # type: Dict[datetime, float]
TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=0)


class FakeArea:
    def __init__(self, count):
        self.current_tick = 2
        self.appliance = None
        self.name = 'FakeArea'
        self.uuid = str(uuid4())
        self.count = count
        self.test_market = FakeMarket(0)
        self._next_market = FakeMarket(0)

    def get_future_market_from_id(self, id):
        return self.test_market

    @property
    def current_market(self):
        return self.test_market

    @property
    def config(self):
        change_global_config(**DEFAULT_CONFIG.__dict__)
        return DEFAULT_CONFIG

    @property
    def now(self) -> DateTime:
        """
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return DateTime.now(tz=TIME_ZONE).start_of('day') + (
            self.config.tick_length * self.current_tick
        )

    @property
    def all_markets(self):
        return [self.test_market]


class FakeAreaTimeSlot(FakeArea):
    def __init__(self):
        super().__init__(0)

    @property
    def all_markets(self):
        return [self._next_market]

    def create_next_market(self, time_slot):
        self._next_market = FakeMarketTimeSlot(time_slot)


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.id = str(count)
        self.created_offers = []
        self.offers = {'id': Offer(id='id', time=pendulum.now(), price=10, energy=0.5, seller='A')}
        self._time_slot = TIME

    def offer(self, price, energy, seller, original_offer_price=None, seller_origin=None,
              seller_origin_id=None, seller_id=None):
        offer = Offer(str(uuid.uuid4()), pendulum.now(), price, energy, seller,
                      original_offer_price, seller_origin=seller_origin,
                      seller_origin_id=seller_origin_id, seller_id=seller_id)
        self.created_offers.append(offer)
        self.offers[offer.id] = offer
        return offer

    @property
    def time_slot(self):
        return self._time_slot

    @property
    def time_slot_str(self):
        return self.time_slot.format(TIME_FORMAT)

    def delete_offer(self, offer_id):
        return


class FakeMarketTimeSlot(FakeMarket):
    def __init__(self, time_slot):
        super().__init__(0)
        self._time_slot = time_slot


class FakeTrade:
    def __init__(self, offer):
        self.offer = offer
        self.seller = "FakeSeller"

    @property
    def buyer(self):
        return "FakeBuyer"


"""TEST1"""


@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def pv_test1(area_test1):
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test1
    p.owner = area_test1
    return p


def test_activation(pv_test1):
    pv_test1.event_activate()
    assert pv_test1.offer_update.number_of_available_updates > 0
    global ENERGY_FORECAST
    ENERGY_FORECAST = pv_test1.state._energy_production_forecast_kWh


"""TEST 3"""


@pytest.fixture()
def area_test3():
    return FakeArea(0)


@pytest.fixture()
def market_test3(area_test3):
    return area_test3.test_market


@pytest.fixture()
def pv_test3(area_test3):
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {Offer('id', pendulum.now(), 30, 1, 'FakeArea'): area_test3.test_market.id}
    return p


def testing_decrease_offer_price(area_test3, market_test3, pv_test3):
    assert len(pv_test3.offers.posted.items()) == 1
    pv_test3.event_activate()
    pv_test3.event_market_cycle()
    old_offer = list(pv_test3.offers.posted.keys())[0]
    area_test3.current_tick += 310
    # in order to mimic at least one past price update:
    pv_test3.offer_update.increment_update_counter_all_markets(pv_test3)
    pv_test3.event_tick()
    new_offer = list(pv_test3.offers.posted.keys())[0]
    assert new_offer.price < old_offer.price


"""TEST 4"""


@pytest.fixture()
def pv_test4(area_test3, called):
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {
        Offer(id='id', time=pendulum.now(), price=20, energy=1,
              seller='FakeArea'): area_test3.test_market.id
    }
    return p


def testing_event_trade(area_test3, pv_test4):
    pv_test4.state._available_energy_kWh[area_test3.test_market.time_slot] = 1
    pv_test4.event_trade(market_id=area_test3.test_market.id,
                         trade=Trade(id='id', time='time',
                                     offer=Offer(id='id', time=pendulum.now(), price=20,
                                                 energy=1, seller='FakeArea'),
                                     seller=area_test3.name, buyer='buyer'
                                     )
                         )
    assert len(pv_test4.offers.open) == 0


"""TEST 5"""


@pytest.fixture()
def pv_test5(area_test3, called):
    p = PVPredefinedStrategy(cloud_coverage=0)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {'id': area_test3.test_market}
    return p


""" TEST 6"""


@pytest.fixture()
def pv_test6(area_test3):
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {}
    return p


@pytest.fixture()
def area_test66():
    return FakeAreaTimeSlot()


@pytest.fixture()
def pv_test66(area_test66):
    p = PVPredefinedStrategy(cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE)
    p.area = area_test66
    p.owner = area_test66
    p.offers.posted = {}
    return p


def testing_produced_energy_forecast_real_data(pv_test66):

    pv_test66.event_activate()
    # prepare whole day of energy_production_forecast_kWh:
    for time_slot in generate_market_slot_list():
        pv_test66.area.create_next_market(time_slot)
        pv_test66.set_produced_energy_forecast_kWh_future_markets(reconfigure=False)

    morning_time = pendulum.today(tz=TIME_ZONE).at(hour=5, minute=10, second=0)
    afternoon_time = pendulum.today(tz=TIME_ZONE).at(hour=19, minute=10, second=0)

    class Counts(object):
        def __init__(self, time):
            self.total = 0
            self.count = 0
            self.time = time
    morning_counts = Counts('morning')
    afternoon_counts = Counts('afternoon')
    evening_counts = Counts('evening')
    for (time, power) in pv_test66.state._energy_production_forecast_kWh.items():
        if time < morning_time:
            morning_counts.total += 1
            morning_counts.count = morning_counts.count + 1 \
                if pv_test66.state._energy_production_forecast_kWh[time] == 0 \
                else morning_counts.count
        elif morning_time < time < afternoon_time:
            afternoon_counts.total += 1
            afternoon_counts.count = afternoon_counts.count + 1 \
                if pv_test66.state._energy_production_forecast_kWh[time] > 0.001 \
                else afternoon_counts.count
        elif time > afternoon_time:
            evening_counts.total += 1
            evening_counts.count = evening_counts.count + 1 \
                if pv_test66.state._energy_production_forecast_kWh[time] == 0 \
                else evening_counts.count

    total_count = morning_counts.total + afternoon_counts.total + evening_counts.total
    assert len(list(pv_test66.state._energy_production_forecast_kWh.items())) == total_count
    morning_count_percent = (morning_counts.count / morning_counts.total) * 100
    assert morning_count_percent > 90

    afternoon_count_percent = (afternoon_counts.count / afternoon_counts.total) * 100
    assert afternoon_count_percent > 90

    evening_count_percent = (evening_counts.count / evening_counts.total) * 100
    assert evening_count_percent > 90


# The pv sells its whole production at once if possible.
# Make sure that it doesnt offer it again after selling.
def test_does_not_offer_sold_energy_again(pv_test6, market_test3):
    pv_test6.event_activate()
    pv_test6.event_market_cycle()
    assert market_test3.created_offers[0].energy == \
        pv_test6.state._energy_production_forecast_kWh[TIME]
    fake_trade = FakeTrade(market_test3.created_offers[0])
    fake_trade.seller = pv_test6.owner.name
    pv_test6.event_trade(market_id=market_test3.id, trade=fake_trade)
    market_test3.created_offers = []
    pv_test6.event_tick()
    assert not market_test3.created_offers


""" TEST 7"""
# Testing with different energy_profiles


@pytest.fixture()
def area_test7():
    return FakeArea(0)


@pytest.fixture()
def pv_test_sunny(area_test3):
    p = PVPredefinedStrategy(cloud_coverage=0)
    p.area = area_test3
    p.owner = area_test3
    return p


@pytest.fixture()
def pv_test_partial(area_test7):
    p = PVPredefinedStrategy(cloud_coverage=2)
    p.area = area_test7
    p.owner = area_test7
    return p


@pytest.fixture()
def pv_test_cloudy(area_test7):
    p = PVPredefinedStrategy(cloud_coverage=1)
    p.area = area_test7
    p.owner = area_test7
    return p


def test_correct_interpolation_power_profile():
    slot_length = 20
    GlobalConfig.slot_length = duration(minutes=slot_length)
    profile_path = pathlib.Path(d3a_path + '/resources/Solar_Curve_W_sunny.csv')
    profile = read_arbitrary_profile(InputProfileTypes.POWER, str(profile_path))
    times = list(profile)
    for ii in range(len(times)-1):
        assert abs((times[ii]-times[ii+1]).in_seconds()) == slot_length * 60


def test_correct_time_expansion_read_arbitrary_profile():
    market_maker_rate = 30
    if IS_CANARY_NETWORK:
        GlobalConfig.sim_duration = duration(hours=3)
        expected_last_time_slot = today(tz=TIME_ZONE).add(days=CN_PROFILE_EXPANSION_DAYS-1,
                                                          hours=23, minutes=45)
        mmr = read_arbitrary_profile(InputProfileTypes.IDENTITY, market_maker_rate)
        assert list(mmr.keys())[-1] == expected_last_time_slot
        GlobalConfig.sim_duration = duration(hours=30)
        expected_last_time_slot = today(tz=TIME_ZONE).add(days=CN_PROFILE_EXPANSION_DAYS-1,
                                                          hours=23, minutes=45)
        mmr = read_arbitrary_profile(InputProfileTypes.IDENTITY, market_maker_rate)
        assert list(mmr.keys())[-1] == expected_last_time_slot
    else:
        GlobalConfig.sim_duration = duration(hours=3)
        mmr = read_arbitrary_profile(InputProfileTypes.IDENTITY, market_maker_rate)
        assert (list(mmr.keys())[-1] - today(tz=TIME_ZONE)).days == 0
        GlobalConfig.sim_duration = duration(hours=36)
        mmr = read_arbitrary_profile(InputProfileTypes.IDENTITY, market_maker_rate)
        assert (list(mmr.keys())[-1] - today(tz=TIME_ZONE)).days == 1
        GlobalConfig.sim_duration = duration(hours=48)
        mmr = read_arbitrary_profile(InputProfileTypes.IDENTITY, market_maker_rate)
        assert list(mmr.keys())[-1] == today(tz=TIME_ZONE).add(days=1, hours=23, minutes=45)
        GlobalConfig.sim_duration = duration(hours=49)
        mmr = read_arbitrary_profile(InputProfileTypes.IDENTITY, market_maker_rate)
        assert list(mmr.keys())[-1] == today(tz=TIME_ZONE).add(days=2, minutes=45)


def test_predefined_pv_constructor_rejects_incorrect_parameters():
    with pytest.raises(D3ADeviceException):
        PVPredefinedStrategy(panel_count=-1)
    with pytest.raises(D3ADeviceException):
        pv = PVPredefinedStrategy(initial_selling_rate=5, final_selling_rate=15)
        pv.event_activate()
    with pytest.raises(D3ADeviceException):
        PVPredefinedStrategy(fit_to_limit=True, energy_rate_decrease_per_update=1)
    with pytest.raises(D3ADeviceException):
        PVPredefinedStrategy(fit_to_limit=False, energy_rate_decrease_per_update=-1)


def test_pv_user_profile_constructor_rejects_incorrect_parameters():
    user_profile_path = os.path.join(d3a_path, "resources/Solar_Curve_W_sunny.csv")
    with pytest.raises(D3ADeviceException):
        PVUserProfileStrategy(power_profile=user_profile_path, panel_count=-1)
    with pytest.raises(D3ADeviceException):
        pv = PVUserProfileStrategy(power_profile=user_profile_path,
                                   initial_selling_rate=5, final_selling_rate=15)
        pv.event_activate()
    with pytest.raises(D3ADeviceException):
        PVUserProfileStrategy(power_profile=user_profile_path,
                              fit_to_limit=True, energy_rate_decrease_per_update=1)
    with pytest.raises(D3ADeviceException):
        PVUserProfileStrategy(power_profile=user_profile_path,
                              fit_to_limit=False, energy_rate_decrease_per_update=-1)


def test_profile_with_date_and_seconds_can_be_parsed():
    GlobalConfig.slot_length = duration(minutes=15)
    profile_date = datetime(year=2019, month=3, day=2)
    GlobalConfig.start_date = profile_date
    profile_path = pathlib.Path(d3a_path + '/resources/datetime_seconds_profile.csv')
    profile = read_arbitrary_profile(InputProfileTypes.POWER, str(profile_path))
    # After the 6th element the rest of the entries are populated with the last value
    expected_energy_values = [1.5, 1.25, 1.0, 0.75, 0.5, 0.25]
    if IS_CANARY_NETWORK:
        energy_values_profile = []
        energy_values_after_profile = []
        end_time = profile_date.add(minutes=GlobalConfig.slot_length.minutes * 6)
        for time, v in profile.items():
            if v > 0:
                if time.weekday() == profile_date.weekday() and time.time() < end_time.time():
                    energy_values_profile.append(v)
                else:
                    energy_values_after_profile.append(v)
        assert energy_values_profile == expected_energy_values
        all(x == 0.25 for x in energy_values_after_profile)
    else:
        assert list(profile.values())[:6] == expected_energy_values
        assert all(x == 0.25 for x in list(profile.values())[6:])

    GlobalConfig.start_date = today(tz=TIME_ZONE)
