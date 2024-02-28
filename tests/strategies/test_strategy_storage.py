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
import logging
from copy import deepcopy
from logging import getLogger
from math import isclose
from uuid import uuid4

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.data_classes import Offer, Trade, BalancingOffer, Bid, TraderDetails
from gsy_framework.exceptions import GSyDeviceException
from gsy_framework.read_user_profile import read_arbitrary_profile, InputProfileTypes
from pendulum import Duration, DateTime, now

from gsy_e.constants import TIME_FORMAT, FLOATING_POINT_TOLERANCE
from gsy_e.constants import TIME_ZONE
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.util import change_global_config
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.state import EnergyOrigin, ESSEnergyOrigin
from gsy_e.models.strategy.storage import StorageStrategy

DeviceRegistry.REGISTRY = {
    "A": (23, 25),
    "someone": (23, 25),
    "seller": (23, 25),
    "FakeArea": (23, 25),
}


@pytest.fixture(scope="function", autouse=True)
def auto_fixture():
    yield
    GlobalConfig.market_maker_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
    ConstSettings.MASettings.MARKET_TYPE = 1


class FakeArea:
    def __init__(self, count):
        self.name = "FakeArea"
        self.uuid = str(uuid4())
        self.count = count
        self.current_tick = 0
        self.past_market = FakeMarket(4)
        self.current_market = FakeMarket(0)
        self.spot_market = self.current_market
        self.test_balancing_market = FakeMarket(1)
        self.children = []

    log = getLogger(__name__)

    @property
    def future_market_time_slots(self):
        return []

    @property
    def future_markets(self):
        return None

    def get_spot_or_future_market_by_id(self, _):
        return self.spot_market

    def is_market_spot_or_future(self, _):
        return True

    def get_balancing_market(self, time):
        return self.test_balancing_market

    @property
    def last_past_market(self):
        return self.past_market

    @property
    def cheapest_offers(self):
        offers = [
            [Offer("id", now(), 12, 0.4, TraderDetails("A", ""))],
            [Offer("id", now(), 12, 0.4, TraderDetails("A", ""))],
            [Offer("id", now(), 20, 1, TraderDetails("A", ""))],
            [Offer("id", now(), 20, 5.1, TraderDetails("A", ""))],
            [Offer("id", now(), 20, 5.1, TraderDetails("A", ""))]
        ]
        return offers[self.count]

    @property
    def past_markets(self):
        return {"past market": self.past_market}

    @property
    def now(self):
        return DateTime.now(tz=TIME_ZONE).start_of("day") + (
                self.config.tick_length * self.current_tick
        )

    @property
    def balancing_markets(self):
        return {self.now: self.test_balancing_market}

    @property
    def config(self):
        configuration = SimulationConfig(
            sim_duration=Duration(hours=24),
            slot_length=Duration(minutes=15),
            tick_length=Duration(seconds=15),
            cloud_coverage=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE,
            market_maker_rate=ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            external_connection_enabled=False
        )
        change_global_config(**configuration.__dict__)
        return configuration


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.id = str(count)
        self.trade = Trade("id", now(), TraderDetails("FakeArea", ""),
                           TraderDetails("buyer", ""), time_slot=self.time_slot,
                           offer=Offer("id", now(), 11.8, 0.5, TraderDetails("FakeArea", "")),
                           traded_energy=0.5, trade_price=11.8)
        self.created_offers = []
        self.offers = {"id": Offer("id", now(), 11.8, 0.5, TraderDetails("FakeArea", "")),
                       "id2": Offer("id2", now(), 20, 0.5, TraderDetails("A", "")),
                       "id3": Offer("id3", now(), 20, 1, TraderDetails("A", "")),
                       "id4": Offer("id4", now(), 19, 5.1, TraderDetails("A", ""))}
        self.bids = {}
        self.created_balancing_offers = []

    @property
    def sorted_offers(self):
        offers = [
            [Offer("id", now(), 11.8, 0.5, TraderDetails("A", ""))],
            [Offer("id2", now(), 20, 0.5, TraderDetails("A", ""))],
            [Offer("id3", now(), 20, 1, TraderDetails("A", ""))],
            [Offer("id4", now(), 19, 5.1, TraderDetails("A", ""))]
        ]
        return offers[self.count]

    def get_offers(self):
        return self.offers

    @property
    def time_slot(self):
        return DateTime.now(tz=TIME_ZONE).start_of("day")

    @property
    def time_slot_str(self):
        return self.time_slot.format(TIME_FORMAT)

    def delete_offer(self, offer_id):
        return

    def offer(self, price, energy, seller, original_price=None, time_slot=None):
        offer = Offer("id", now(), price, energy, seller, original_price)
        self.created_offers.append(offer)
        return offer

    def balancing_offer(self, price, energy, seller):
        offer = BalancingOffer("id", now(), price, energy, seller)
        self.created_balancing_offers.append(offer)
        offer.id = "id"
        return offer

    def bid(self, price, energy, buyer, market=None, original_price=None):
        pass


"""TEST1"""


# Test if storage buys cheap energy

@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def storage_strategy_test1(area_test1, called):
    s = StorageStrategy(max_abs_battery_power_kW=2.01,
                        initial_buying_rate=23.6, final_buying_rate=23.6,
                        initial_selling_rate=23.7, final_selling_rate=23.7)
    s.owner = area_test1
    s.area = area_test1
    s.accept_offer = called
    return s


def test_if_storage_buys_cheap_energy(storage_strategy_test1, area_test1):
    storage_strategy_test1.event_activate()
    storage_strategy_test1.event_tick()
    for i in range(5):
        area_test1.current_tick += 310
        storage_strategy_test1.event_tick()
    assert storage_strategy_test1.accept_offer.calls[0][0][1] == repr(
        FakeMarket(0).sorted_offers[0])


"""TEST2"""


# Test if storage doesn't buy energy for more than 30ct

@pytest.fixture()
def area_test2():
    return FakeArea(1)


@pytest.fixture()
def storage_strategy_test2(area_test2, called):
    s = StorageStrategy(max_abs_battery_power_kW=2.01)
    s.owner = area_test2
    s.area = area_test2
    s.accept_offer = called
    return s


def test_if_storage_doesnt_buy_30ct(storage_strategy_test2, area_test2):
    storage_strategy_test2.event_activate()
    storage_strategy_test2.event_tick()
    assert len(storage_strategy_test2.accept_offer.calls) == 0


def test_if_storage_doesnt_buy_above_break_even_point(storage_strategy_test2, area_test2):
    storage_strategy_test2.event_activate()
    storage_strategy_test2.break_even_buy = 10.0
    area_test2.current_market.offers = {"id": Offer("id", now(), 10.1, 1,
                                                    TraderDetails("FakeArea", ""),
                                                    10.1)}
    storage_strategy_test2.event_tick()
    assert len(storage_strategy_test2.accept_offer.calls) == 0
    area_test2.current_market.offers = {"id": Offer("id", now(), 9.9, 1,
                                                    TraderDetails("FakeArea", ""),
                                                    9.9)}

    storage_strategy_test2.event_tick()
    assert len(storage_strategy_test2.accept_offer.calls) == 0


"""TEST3"""


# Test if storage doesn't buy for over avg price

@pytest.fixture()
def area_test3():
    return FakeArea(2)


@pytest.fixture()
def storage_strategy_test3(area_test3, called):
    s = StorageStrategy(max_abs_battery_power_kW=2.01)
    s.owner = area_test3
    s.area = area_test3
    s.accept_offer = called
    return s


def test_if_storage_doesnt_buy_too_expensive(storage_strategy_test3, area_test3):
    storage_strategy_test3.bid_update.initial_rate = \
        read_arbitrary_profile(InputProfileTypes.IDENTITY, 0)
    storage_strategy_test3.bid_update.final_rate = \
        read_arbitrary_profile(InputProfileTypes.IDENTITY, 1)
    storage_strategy_test3.event_activate()
    storage_strategy_test3.event_tick()
    assert len(storage_strategy_test3.accept_offer.calls) == 0


@pytest.fixture()
def storage_strategy_test_buy_energy(area_test3, called):
    s = StorageStrategy(max_abs_battery_power_kW=20.01, initial_buying_rate=24)
    s.owner = area_test3
    s.area = area_test3
    s.accept_offer = called
    return s


def test_if_storage_buys_below_break_even(storage_strategy_test_buy_energy, area_test3):
    storage_strategy_test_buy_energy.event_activate()
    storage_strategy_test_buy_energy.event_tick()

    assert len(storage_strategy_test_buy_energy.accept_offer.calls) == 1


"""TEST4"""


# Test if storage pays respect to its capacity


@pytest.fixture()
def area_test4():
    return FakeArea(3)


@pytest.fixture()
def storage_strategy_test4(area_test4, called):
    s = StorageStrategy(initial_soc=100,
                        battery_capacity_kWh=2.1)
    s.owner = area_test4
    s.area = area_test4
    s.accept_offer = called
    return s


def test_if_storage_pays_respect_to_capacity_limits(storage_strategy_test4, area_test4):
    storage_strategy_test4.event_activate()
    storage_strategy_test4.event_tick()
    assert len(storage_strategy_test4.accept_offer.calls) == 0


"""TEST5"""


# Test if internal storage is handled correctly

@pytest.fixture()
def area_test5():
    return FakeArea(4)


@pytest.fixture()
def storage_strategy_test5(area_test5, called):
    s = StorageStrategy(initial_soc=100, battery_capacity_kWh=5)
    s.owner = area_test5
    s.area = area_test5
    s._sell_energy_to_spot_market = called
    area_test5.past_market.offers = {
        "id": Offer("id", now(), 20, 1, TraderDetails("A", "")),
        "id2": Offer("id2", now(), 20, 3, TraderDetails("FakeArea", "")),
        "id3": Offer("id3", now(), 100, 1, TraderDetails("FakeArea", ""))
    }

    s.offers.bought_offer(area_test5.past_market.offers["id"], area_test5.past_market.id)
    s.offers.post(area_test5.past_market.offers["id3"], area_test5.past_market.id)
    s.offers.post(area_test5.past_market.offers["id2"], area_test5.past_market.id)
    s.offers.sold_offer(area_test5.past_market.offers["id2"], area_test5.past_market)
    assert s.state.used_storage == 5
    return s


def test_if_storage_handles_capacity_correctly(storage_strategy_test5, area_test5):
    storage_strategy_test5.event_activate()
    storage_strategy_test5.event_market_cycle()
    assert storage_strategy_test5.state.used_storage == 5
    assert len(storage_strategy_test5._sell_energy_to_spot_market.calls) == 1


"""TEST6"""


# Test if trades are handled correctly

@pytest.fixture()
def area_test6():
    return FakeArea(0)


@pytest.fixture
def market_test6():
    return FakeMarket(0)


@pytest.fixture()
def storage_strategy_test6(area_test6, market_test6, called):
    s = StorageStrategy(initial_soc=41.67)
    s.owner = area_test6
    s.area = area_test6
    s.accept_offer = called
    s.offers.post(market_test6.trade.match_details["offer"], market_test6.id)
    s.event_activate()
    return s


def test_if_trades_are_handled_correctly(storage_strategy_test6, market_test6):
    storage_strategy_test6.area.get_future_market_from_id = (
        lambda _id: market_test6 if _id == market_test6.id else None)
    storage_strategy_test6.state.add_default_values_to_state_profiles(
        [storage_strategy_test6.spot_market_time_slot])
    storage_strategy_test6.event_offer_traded(market_id=market_test6.id, trade=market_test6.trade)
    assert (market_test6.trade.match_details["offer"] in
            storage_strategy_test6.offers.sold[market_test6.id])
    assert market_test6.trade.match_details["offer"] not in storage_strategy_test6.offers.open


"""TEST7"""


# Testing the sell energy function
@pytest.fixture()
def area_test7():
    return FakeArea(4)


@pytest.fixture()
def storage_strategy_test7(area_test7):
    s = StorageStrategy(initial_soc=99.667, battery_capacity_kWh=3.01,
                        max_abs_battery_power_kW=5.21, initial_buying_rate=31,
                        final_buying_rate=31, initial_selling_rate=32,
                        final_selling_rate=32)
    s.owner = area_test7
    s.area = area_test7
    return s


def test_sell_energy_function(storage_strategy_test7, area_test7: FakeArea):
    storage_strategy_test7.event_activate()
    sell_market = area_test7.spot_market
    energy_sell_dict = \
        storage_strategy_test7.state._clamp_energy_to_sell_kWh([sell_market.time_slot])
    storage_strategy_test7.event_market_cycle()
    assert (isclose(storage_strategy_test7.state.offered_sell_kWh[sell_market.time_slot],
                    energy_sell_dict[sell_market.time_slot], rel_tol=1e-03))
    assert (isclose(storage_strategy_test7.state.used_storage, 3.0, rel_tol=1e-03))
    assert len(storage_strategy_test7.offers.posted_in_market(sell_market.id)) > 0


@pytest.mark.skip("ESS IS NOT REDUCING OFFER RATE ATM")
def test_calculate_sell_energy_rate_lower_bound(storage_strategy_test7):
    storage_strategy_test7.event_activate()
    market = storage_strategy_test7.area.current_market
    final_selling_rate = storage_strategy_test7.offer_update.final_rate
    assert (isclose(storage_strategy_test7.calculate_selling_rate(market),
                    final_selling_rate[market.time_slot]))


@pytest.fixture()
def storage_strategy_test7_1(area_test7):
    s = StorageStrategy(initial_soc=99.67, battery_capacity_kWh=3.01,
                        max_abs_battery_power_kW=5.21, final_buying_rate=26,
                        final_selling_rate=27)
    s.owner = area_test7
    s.area = area_test7
    return s


def test_calculate_initial_sell_energy_rate_upper_bound(storage_strategy_test7_1):
    storage_strategy_test7_1.event_activate()
    market = storage_strategy_test7_1.area.current_market
    market_maker_rate = \
        storage_strategy_test7_1.simulation_config.market_maker_rate[market.time_slot]
    assert storage_strategy_test7_1.calculate_selling_rate(market) == market_maker_rate


@pytest.fixture()
def storage_strategy_test7_3(area_test7):
    s = StorageStrategy(initial_soc=19.96, battery_capacity_kWh=5.01,
                        max_abs_battery_power_kW=5.21, final_selling_rate=17,
                        initial_buying_rate=15, final_buying_rate=16)
    s.owner = area_test7
    s.area = area_test7
    s.offers.posted = {Offer("id", now(),
                             30, 1, TraderDetails("FakeArea", "")): area_test7.current_market.id}
    s.market = area_test7.current_market
    return s


def test_calculate_energy_amount_to_sell_respects_min_allowed_soc(storage_strategy_test7_3,
                                                                  area_test7):
    storage_strategy_test7_3.event_activate()
    time_slot = area_test7.current_market.time_slot
    energy_sell_dict = storage_strategy_test7_3.state._clamp_energy_to_sell_kWh(
        [time_slot])
    target_energy = (storage_strategy_test7_3.state.used_storage
                     - storage_strategy_test7_3.state.pledged_sell_kWh[time_slot]
                     - storage_strategy_test7_3.state.offered_sell_kWh[time_slot]
                     - storage_strategy_test7_3.state.capacity
                     * storage_strategy_test7_3.state.min_allowed_soc_ratio)

    assert (isclose(energy_sell_dict[time_slot], target_energy, rel_tol=1e-03))


def test_clamp_energy_to_buy(storage_strategy_test7_3):
    storage_strategy_test7_3.event_activate()
    storage_strategy_test7_3.state._battery_energy_per_slot = 0.5
    time_slot = storage_strategy_test7_3.market.time_slot
    storage_strategy_test7_3.state._clamp_energy_to_buy_kWh([time_slot])
    assert storage_strategy_test7_3.state.energy_to_buy_dict[time_slot] == \
           storage_strategy_test7_3.state._battery_energy_per_slot

    # Reduce used storage below battery_energy_per_slot

    storage_strategy_test7_3.state._used_storage = 4.6
    assert isclose(storage_strategy_test7_3.state.free_storage(time_slot), 0.41)
    storage_strategy_test7_3.state._clamp_energy_to_buy_kWh([time_slot])
    assert isclose(storage_strategy_test7_3.state.energy_to_buy_dict[time_slot], 0.41)


"""TEST8"""


# Testing the sell energy function
@pytest.fixture()
def area_test8():
    return FakeArea(4)


@pytest.fixture()
def storage_strategy_test8(area_test8):
    s = StorageStrategy(initial_soc=99, battery_capacity_kWh=101,
                        max_abs_battery_power_kW=401)
    s.owner = area_test8
    s.area = area_test8
    return s


def test_sell_energy_function_with_stored_capacity(storage_strategy_test8, area_test8: FakeArea):
    storage_strategy_test8.event_activate()
    storage_strategy_test8.event_market_cycle()
    sell_market = area_test8.spot_market
    assert abs(storage_strategy_test8.state.used_storage
               - storage_strategy_test8.state.offered_sell_kWh[sell_market.time_slot] -
               storage_strategy_test8.state.capacity *
               storage_strategy_test8.state.min_allowed_soc_ratio) < FLOATING_POINT_TOLERANCE
    assert (isclose(storage_strategy_test8.state.offered_sell_kWh[sell_market.time_slot],
                    100 - storage_strategy_test8.state.capacity *
                    storage_strategy_test8.state.min_allowed_soc_ratio, rel_tol=1e-02))

    assert (isclose(area_test8.spot_market.created_offers[0].energy,
                    100 - storage_strategy_test8.state.capacity *
                    storage_strategy_test8.state.min_allowed_soc_ratio, rel_tol=1e-02))
    assert len(storage_strategy_test8.offers.posted_in_market(
        area_test8.spot_market.id)
    ) > 0


"""TEST9"""


# Test if initial capacity is sold
def test_first_market_cycle_with_initial_capacity(storage_strategy_test8: StorageStrategy,
                                                  area_test8: FakeArea):
    storage_strategy_test8.event_activate()
    storage_strategy_test8.event_market_cycle()
    sell_market = area_test8.spot_market
    assert (isclose(storage_strategy_test8.state.offered_sell_kWh[sell_market.time_slot],
                    100.0 - storage_strategy_test8.state.capacity *
                    storage_strategy_test8.state.min_allowed_soc_ratio, rel_tol=1e-02))
    assert len(storage_strategy_test8.offers.posted_in_market(
        area_test8.spot_market.id)
    ) > 0


"""TEST10"""


# Handling of initial_charge parameter
def test_initial_charge(caplog):
    with caplog.at_level(logging.INFO):
        storage = StorageStrategy(initial_soc=60)
    assert storage.state.used_storage == 0.6 * storage.state.capacity


def test_storage_constructor_rejects_incorrect_parameters():
    with pytest.raises(GSyDeviceException):
        StorageStrategy(battery_capacity_kWh=-1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(initial_soc=101)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(initial_soc=-1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(initial_selling_rate=-1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(final_selling_rate=-1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(initial_selling_rate=1, final_selling_rate=5)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(initial_buying_rate=-1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(final_buying_rate=-1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(initial_buying_rate=10, final_buying_rate=1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(initial_selling_rate=-1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(fit_to_limit=True, energy_rate_decrease_per_update=1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(fit_to_limit=False, energy_rate_decrease_per_update=-1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(fit_to_limit=True, energy_rate_increase_per_update=1)
    with pytest.raises(GSyDeviceException):
        StorageStrategy(fit_to_limit=False, energy_rate_increase_per_update=-1)


def test_free_storage_calculation_takes_into_account_storage_capacity(storage_strategy_test1):
    time_slot = storage_strategy_test1.area.spot_market.time_slot
    for capacity in [50.0, 100.0, 1000.0]:
        storage_strategy_test1.state.pledged_sell_kWh[time_slot] = 12.0
        storage_strategy_test1.state.pledged_buy_kWh[time_slot] = 13.0
        storage_strategy_test1.state.offered_buy_kWh[time_slot] = 14.0
        storage_strategy_test1.state.capacity = capacity

        assert storage_strategy_test1.state.free_storage(time_slot) == \
               storage_strategy_test1.state.capacity \
               + storage_strategy_test1.state.pledged_sell_kWh[time_slot] \
               - storage_strategy_test1.state.pledged_buy_kWh[time_slot] \
               - storage_strategy_test1.state.used_storage


"""TEST11"""


@pytest.fixture()
def area_test11():
    return FakeArea(0)


@pytest.fixture()
def storage_strategy_test11(area_test11, called):
    s = StorageStrategy(battery_capacity_kWh=100, initial_soc=50,
                        max_abs_battery_power_kW=1, initial_buying_rate=30,
                        final_buying_rate=30, initial_selling_rate=33, final_selling_rate=32)
    s.owner = area_test11
    s.area = area_test11
    s.accept_offer = called
    s.event_activate()
    return s


def test_storage_buys_partial_offer_and_respecting_battery_power(storage_strategy_test11,
                                                                 area_test11):
    storage_strategy_test11.event_activate()
    buy_market = area_test11.spot_market
    storage_strategy_test11.event_tick()
    for i in range(2):
        area_test11.current_tick += 310
        storage_strategy_test11.event_tick()
    # storage should not be able to buy energy after this tick because
    # self.state._battery_energy_per_slot is exceeded
    te = storage_strategy_test11.state.energy_to_buy_dict[buy_market.time_slot]
    assert te == 0.
    assert len(storage_strategy_test11.accept_offer.calls) >= 1


def test_has_battery_reached_max_power(storage_strategy_test11):
    storage_strategy_test11.event_activate()
    time_slot = storage_strategy_test11.area.spot_market.time_slot
    storage_strategy_test11.state.pledged_sell_kWh[time_slot] = 5
    storage_strategy_test11.state.offered_sell_kWh[time_slot] = 5
    storage_strategy_test11.state.pledged_buy_kWh[time_slot] = 5
    storage_strategy_test11.state.offered_buy_kWh[time_slot] = 5
    assert storage_strategy_test11.state._has_battery_reached_max_discharge_power(
        1, time_slot) is True
    assert storage_strategy_test11.state._has_battery_reached_max_discharge_power(
        0.25, time_slot) is False


"""TEST12"""


@pytest.fixture()
def area_test12():
    return FakeArea(0)


@pytest.fixture
def market_test7():
    return FakeMarket(0)


@pytest.fixture()
def storage_strategy_test12(area_test12):
    s = StorageStrategy(battery_capacity_kWh=5, max_abs_battery_power_kW=5,
                        cap_price_strategy=True)
    s.owner = area_test12
    s.area = area_test12
    return s


def test_storage_capacity_dependant_sell_rate(storage_strategy_test12, market_test7):
    storage_strategy_test12.event_activate()
    max_selling_rate = storage_strategy_test12.offer_update.initial_rate[market_test7.time_slot]
    min_selling_rate = storage_strategy_test12.offer_update.final_rate[market_test7.time_slot]
    used_storage = storage_strategy_test12.state.used_storage
    battery_capacity_kWh = storage_strategy_test12.state.capacity
    soc = used_storage / battery_capacity_kWh
    actual_rate = storage_strategy_test12.calculate_selling_rate(market_test7)
    expected_rate = max_selling_rate - (max_selling_rate - min_selling_rate) * soc
    assert actual_rate == expected_rate


"""TEST13"""


@pytest.fixture()
def area_test13():
    return FakeArea(0)


@pytest.fixture
def market_test13():
    return FakeMarket(0)


@pytest.fixture()
def storage_strategy_test13(area_test13, called):
    s = StorageStrategy(battery_capacity_kWh=5, max_abs_battery_power_kW=5,
                        initial_selling_rate=35.1, final_selling_rate=35,
                        initial_buying_rate=34, final_buying_rate=34)
    s.owner = area_test13
    s.area = area_test13
    s.accept_offer = called
    return s


def test_storage_event_trade(storage_strategy_test11, market_test13):
    storage_strategy_test11.state.add_default_values_to_state_profiles(
        [storage_strategy_test11.spot_market_time_slot])
    storage_strategy_test11.event_offer_traded(market_id=market_test13.id,
                                               trade=market_test13.trade)
    assert storage_strategy_test11.state.pledged_sell_kWh[market_test13.time_slot] == \
           market_test13.trade.traded_energy
    assert storage_strategy_test11.state.offered_sell_kWh[
               market_test13.time_slot] == -market_test13.trade.traded_energy


def test_balancing_offers_are_not_created_if_device_not_in_registry(
        storage_strategy_test13, area_test13):
    DeviceRegistry.REGISTRY = {}
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    storage_strategy_test13.event_activate()
    storage_strategy_test13.event_market_cycle()
    storage_strategy_test13.event_balancing_market_cycle()
    assert len(area_test13.test_balancing_market.created_balancing_offers) == 0
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = False


def test_balancing_offers_are_created_if_device_in_registry(
        storage_strategy_test13, area_test13):
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    DeviceRegistry.REGISTRY = {"FakeArea": (30, 40)}
    storage_strategy_test13.event_activate()
    storage_strategy_test13.event_market_cycle()
    storage_strategy_test13.event_balancing_market_cycle()
    storage_slot_market = storage_strategy_test13.area.spot_market
    assert len(area_test13.test_balancing_market.created_balancing_offers) == 2
    actual_balancing_demand_energy = \
        area_test13.test_balancing_market.created_balancing_offers[0].energy

    expected_balancing_demand_energy = \
        -1 * storage_strategy_test13.balancing_energy_ratio.demand * \
        storage_strategy_test13.state.free_storage(storage_slot_market.time_slot)
    assert actual_balancing_demand_energy == expected_balancing_demand_energy
    actual_balancing_demand_price = \
        area_test13.test_balancing_market.created_balancing_offers[0].price
    assert actual_balancing_demand_price == abs(expected_balancing_demand_energy) * 30
    actual_balancing_supply_energy = \
        area_test13.test_balancing_market.created_balancing_offers[1].energy
    expected_balancing_supply_energy = \
        storage_strategy_test13.state.used_storage * \
        storage_strategy_test13.balancing_energy_ratio.supply
    assert actual_balancing_supply_energy == expected_balancing_supply_energy
    actual_balancing_supply_price = \
        area_test13.test_balancing_market.created_balancing_offers[1].price
    assert actual_balancing_supply_price == expected_balancing_supply_energy * 40
    DeviceRegistry.REGISTRY = {}
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = False


"""TEST14"""


@pytest.fixture()
def area_test14():
    return FakeArea(0)


@pytest.fixture
def market_test14():
    return FakeMarket(0)


@pytest.fixture()
def storage_strategy_test14(area_test14, called):
    s = StorageStrategy(initial_soc=50, battery_capacity_kWh=30,
                        max_abs_battery_power_kW=10, initial_selling_rate=25,
                        final_selling_rate=24, initial_buying_rate=0, final_buying_rate=23.9)
    s.owner = area_test14
    s.area = area_test14
    s.accept_offer = called
    return s


def test_initial_selling_rate(storage_strategy_test14, area_test14):
    storage_strategy_test14.event_activate()
    storage_strategy_test14.event_market_cycle()
    created_offer = area_test14.spot_market.created_offers[0]
    assert created_offer.price / created_offer.energy == 25


"""TEST15"""


@pytest.fixture()
def area_test15():
    return FakeArea(0)


@pytest.fixture
def market_test15():
    return FakeMarket(0)


@pytest.fixture()
def storage_strategy_test15(area_test15, called):
    s = StorageStrategy(initial_soc=50, battery_capacity_kWh=30,
                        max_abs_battery_power_kW=10, initial_selling_rate=25,
                        final_selling_rate=25, initial_buying_rate=24,
                        final_buying_rate=24)
    s.owner = area_test15
    s.area = deepcopy(area_test15)
    s.area.parent = deepcopy(area_test15)
    s.owner.name = "Storage"
    s.area.parent.name = "ParentArea"
    s.area.children = deepcopy([area_test15])
    s.area.children[0].name = "OtherChildArea"
    s.accept_offer = called
    return s


def test_energy_origin(storage_strategy_test15, market_test15):
    storage_strategy_test15.event_activate()
    assert len(storage_strategy_test15.state._used_storage_share) == 1
    assert storage_strategy_test15.state._used_storage_share[0] == EnergyOrigin(
        ESSEnergyOrigin.EXTERNAL, 15)

    # Validate that local energy origin is correctly registered
    current_market = storage_strategy_test15.area.current_market
    offer = Offer("id", now(), 20, 1.0, TraderDetails("OtherChildArea", ""))
    storage_strategy_test15._try_to_buy_offer(offer, current_market, 21)
    storage_strategy_test15.area.current_market.trade = Trade(
        "id", now(), TraderDetails("OtherChildArea", ""), TraderDetails("Storage", ""),
        offer=offer, traded_energy=1, trade_price=20)
    storage_strategy_test15.event_offer_traded(market_id=market_test15.id,
                                               trade=current_market.trade)
    assert len(storage_strategy_test15.state._used_storage_share) == 2
    assert storage_strategy_test15.state._used_storage_share == [EnergyOrigin(
        ESSEnergyOrigin.EXTERNAL, 15), EnergyOrigin(ESSEnergyOrigin.LOCAL, 1)]

    # Validate that local energy origin with the same seller / buyer is correctly registered
    offer = Offer("id", now(), 20, 2.0, TraderDetails("Storage", ""))
    storage_strategy_test15._try_to_buy_offer(offer, current_market, 21)
    storage_strategy_test15.area.current_market.trade = Trade(
        "id", now(), TraderDetails("Storage", ""), TraderDetails("A", ""),
        time_slot=current_market.time_slot,
        offer=offer, traded_energy=2, trade_price=20)
    storage_strategy_test15.event_offer_traded(
        market_id=market_test15.id,
        trade=current_market.trade)
    assert len(storage_strategy_test15.state._used_storage_share) == 2
    assert storage_strategy_test15.state._used_storage_share == [EnergyOrigin(
        ESSEnergyOrigin.EXTERNAL, 13), EnergyOrigin(ESSEnergyOrigin.LOCAL, 1)]

    # Validate that external energy origin is correctly registered
    offer = Offer("id", now(), 20, 1.0, TraderDetails("FakeArea", ""))
    storage_strategy_test15._try_to_buy_offer(offer, current_market, 21)
    current_market.trade = Trade(
        "id", now(), TraderDetails("FakeArea", ""), TraderDetails("Storage", ""),
        offer=offer, traded_energy=1, trade_price=20)
    storage_strategy_test15.event_offer_traded(
        market_id=market_test15.id,
        trade=current_market.trade)
    assert len(storage_strategy_test15.state._used_storage_share) == 3
    assert storage_strategy_test15.state._used_storage_share == [EnergyOrigin(
        ESSEnergyOrigin.EXTERNAL, 13.0), EnergyOrigin(ESSEnergyOrigin.LOCAL, 1.0),
        EnergyOrigin(ESSEnergyOrigin.EXTERNAL, 1.0)]


def test_storage_strategy_increases_rate_when_fit_to_limit_is_false():
    storage = StorageStrategy(
        fit_to_limit=False,
        initial_selling_rate=30, final_selling_rate=25, energy_rate_decrease_per_update=1,
        initial_buying_rate=10, final_buying_rate=20, energy_rate_increase_per_update=1)
    storage.area = FakeArea(1)
    storage.event_activate()
    assert all([rate == -1 for rate in storage.bid_update.energy_rate_change_per_update.values()])
    assert all([rate == 1 for rate in storage.offer_update.energy_rate_change_per_update.values()])


"""Test 16"""


@pytest.fixture()
def storage_test11(area_test3):
    s = StorageStrategy()
    s.area = area_test3
    s.owner = area_test3
    return s


def test_assert_if_trade_rate_is_lower_than_offer_rate(storage_test11):
    market_id = "market_id"
    storage_test11.offers.sold[market_id] = [
        Offer("offer_id", now(), 30, 1, TraderDetails("FakeArea", ""))]
    too_cheap_offer = Offer("offer_id", now(), 29, 1, TraderDetails("FakeArea", ""))
    trade = Trade("trade_id", now(), TraderDetails("FakeArea", ""), TraderDetails("buyer", ""),
                  offer=too_cheap_offer, traded_energy=1, trade_price=29)

    with pytest.raises(AssertionError):
        storage_test11.event_offer_traded(market_id=market_id, trade=trade)


def test_assert_if_trade_rate_is_higher_than_bid_rate(storage_test11):
    market_id = "2"
    storage_test11.area.spot_market.id = market_id
    storage_test11._bids[market_id] = [
        Bid("bid_id", now(), 30, 1, buyer=TraderDetails("FakeArea", ""))]
    expensive_bid = Bid("bid_id", now(), 31, 1, buyer=TraderDetails("FakeArea", ""))
    trade = Trade("trade_id", now(), TraderDetails("FakeArea", ""), TraderDetails("FakeArea", ""),
                  bid=expensive_bid, traded_energy=1, trade_price=31,
                  time_slot=storage_test11.area.spot_market.time_slot)
    with pytest.raises(AssertionError):
        storage_test11.event_offer_traded(market_id=market_id, trade=trade)
