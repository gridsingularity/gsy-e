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
import os
import pathlib
import uuid
from typing import Dict  # NOQA
from uuid import uuid4

import pendulum
import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.data_classes import Offer, TraderDetails
from gsy_framework.exceptions import GSyDeviceException
from gsy_framework.read_user_profile import read_arbitrary_profile, InputProfileTypes
from gsy_framework.utils import generate_market_slot_list
from gsy_framework.enums import ConfigurationType
from pendulum import DateTime, duration, datetime

from gsy_e.constants import TIME_ZONE, TIME_FORMAT
from gsy_e.gsy_e_core.util import gsye_root_path, change_global_config
from gsy_e.models.config import create_simulation_config_from_global_config
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy

DEFAULT_CONFIG = create_simulation_config_from_global_config()


def setup_function():
    change_global_config(**DEFAULT_CONFIG.__dict__)


@pytest.fixture(scope="function", autouse=True)
def auto_fixture():
    yield
    GlobalConfig.sim_duration = duration(days=GlobalConfig.DURATION_D)
    GlobalConfig.slot_length = duration(minutes=GlobalConfig.SLOT_LENGTH_M)


ENERGY_FORECAST = {}  # type: Dict[datetime, float]
TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=0)


class FakeArea:
    def __init__(self, count):
        self.current_tick = 2
        self.name = 'FakeArea'
        self.uuid = str(uuid4())
        self.count = count
        self.test_market = FakeMarket(0)
        self._spot_market = FakeMarket(0)

    @property
    def future_markets(self):
        return None

    def get_spot_or_future_market_by_id(self, _):
        return self.test_market

    def is_market_spot_or_future(self, _):
        return True

    @property
    def current_market(self):
        return self.test_market

    @property
    def spot_market(self):
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
    def spot_market(self):
        return self._spot_market

    def create_spot_market(self, time_slot):
        self._spot_market = FakeMarketTimeSlot(time_slot)


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.id = str(count)
        self.created_offers = []
        self.offers = {
            'id': Offer(id='id', creation_time=pendulum.now(), price=10, energy=0.5,
                        seller=TraderDetails("A", ""))}
        self._time_slot = TIME

    def offer(self, price, energy, seller, original_price=None, time_slot=None):
        offer = Offer(str(uuid.uuid4()), pendulum.now(), price, energy, seller,
                      original_price, time_slot=time_slot)
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
        self.match_details = {"offer": offer, "bid": None}
        self.seller = TraderDetails("FakeSeller", "")
        self.traded_energy = offer.energy
        self.trade_price = offer.price

    @property
    def is_offer_trade(self):
        return True

    @property
    def buyer(self):
        return "FakeBuyer"

    @property
    def trade_rate(self):
        return self.offer.energy_rate


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
    p.offers.posted = {Offer('id', pendulum.now(), 30, 1,
                             TraderDetails("FakeArea", "")): area_test3.test_market.id}
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
        Offer(id='id', creation_time=pendulum.now(), price=20, energy=1,
              seller=TraderDetails("FakeArea", "")): area_test3.test_market.id
    }
    return p


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
        pv_test66.area.create_spot_market(time_slot)
        pv_test66.set_produced_energy_forecast_in_state(reconfigure=False)

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
    fake_trade.seller = TraderDetails(
        pv_test6.owner.name, fake_trade.seller.uuid,
        fake_trade.seller.origin, fake_trade.seller.origin_uuid)
    fake_trade.time_slot = market_test3.time_slot
    pv_test6.event_offer_traded(market_id=market_test3.id, trade=fake_trade)
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
    original_slot_length = GlobalConfig.slot_length
    GlobalConfig.slot_length = duration(minutes=slot_length)
    profile_path = pathlib.Path(gsye_root_path + "/resources/Solar_Curve_W_sunny.csv")
    profile = read_arbitrary_profile(InputProfileTypes.POWER_W, str(profile_path))
    times = list(profile)
    for ii in range(len(times)-1):
        assert abs((times[ii]-times[ii+1]).in_seconds()) == slot_length * 60
    GlobalConfig.slot_length = original_slot_length


def test_predefined_pv_constructor_rejects_incorrect_parameters():
    with pytest.raises(GSyDeviceException):
        PVPredefinedStrategy(panel_count=-1)
    with pytest.raises(GSyDeviceException):
        pv = PVPredefinedStrategy(initial_selling_rate=5, final_selling_rate=15)
        pv.event_activate()
    with pytest.raises(GSyDeviceException):
        PVPredefinedStrategy(fit_to_limit=True, energy_rate_decrease_per_update=1)
    with pytest.raises(GSyDeviceException):
        PVPredefinedStrategy(fit_to_limit=False, energy_rate_decrease_per_update=-1)


def test_pv_user_profile_constructor_rejects_incorrect_parameters():
    user_profile_path = os.path.join(gsye_root_path, "resources/Solar_Curve_W_sunny.csv")
    with pytest.raises(GSyDeviceException):
        PVUserProfileStrategy(power_profile=user_profile_path, panel_count=-1)
    with pytest.raises(GSyDeviceException):
        pv = PVUserProfileStrategy(power_profile=user_profile_path,
                                   initial_selling_rate=5, final_selling_rate=15)
        pv.event_activate()
    with pytest.raises(GSyDeviceException):
        PVUserProfileStrategy(power_profile=user_profile_path,
                              fit_to_limit=True, energy_rate_decrease_per_update=1)
    with pytest.raises(GSyDeviceException):
        PVUserProfileStrategy(power_profile=user_profile_path,
                              fit_to_limit=False, energy_rate_decrease_per_update=-1)


@pytest.mark.parametrize("is_canary", [False, True])
def test_profile_with_date_and_seconds_can_be_parsed(is_canary):
    original_start_date = GlobalConfig.start_date
    original_config_type = GlobalConfig.CONFIG_TYPE
    original_slot_length = GlobalConfig.slot_length
    if is_canary:
        GlobalConfig.CONFIG_TYPE = ConfigurationType.CANARY_NETWORK.value
    GlobalConfig.slot_length = duration(minutes=15)
    profile_date = datetime(year=2019, month=3, day=2)
    GlobalConfig.start_date = profile_date
    profile_path = pathlib.Path(gsye_root_path + "/resources/datetime_seconds_profile.csv")
    profile = read_arbitrary_profile(InputProfileTypes.POWER_W, str(profile_path))
    # After the 6th element the rest of the entries are populated with the last value
    expected_energy_values = [1.5, 1.25, 1.0, 0.75, 0.5, 0.25]
    if GlobalConfig.is_canary_network():
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

    GlobalConfig.start_date = original_start_date
    GlobalConfig.CONFIG_TYPE = original_config_type
    GlobalConfig.slot_length = original_slot_length
