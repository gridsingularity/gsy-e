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
import unittest
from copy import deepcopy
from math import isclose
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.data_classes import Offer, BalancingOffer, Bid, Trade, TraderDetails
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.exceptions import GSyDeviceException
from pendulum import DateTime, duration, today, now

from gsy_e.constants import TIME_ZONE, TIME_FORMAT
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import Area
from gsy_e.models.config import create_simulation_config_from_global_config
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy

TIME = today(tz=TIME_ZONE).at(hour=10, minute=45, second=0)

MIN_BUY_ENERGY = 50  # wh


@pytest.fixture(scope="function", autouse=True)
def auto_fixture():
    original_market_maker_rate = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
    yield
    GlobalConfig.market_maker_rate = original_market_maker_rate
    ConstSettings.MASettings.MARKET_TYPE = 1


class FakeArea:
    def __init__(self):
        self.config = create_simulation_config_from_global_config()
        self.name = 'FakeArea'
        self.uuid = str(uuid4())

        self._spot_market = FakeMarket(0)
        self.current_market = FakeMarket(0)
        self._bids = {}
        self.markets = {TIME: self.current_market,
                        TIME + self.config.slot_length: FakeMarket(0),
                        TIME + 2 * self.config.slot_length: FakeMarket(0)}
        self.test_balancing_market = FakeMarket(1)
        self.test_balancing_market_2 = FakeMarket(2)

    def get_spot_or_future_market_by_id(self, _):
        return self._spot_market

    def is_market_spot_or_future(self, _):
        return True

    def get_path_to_root_fees(self):
        return 0.

    @property
    def future_markets(self):
        return None

    @property
    def future_market_time_slots(self):
        return []

    @property
    def all_markets(self):
        return list(self.markets.values())

    @property
    def current_tick(self):
        return 5

    @property
    def now(self) -> DateTime:
        """
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return DateTime.now(tz=TIME_ZONE).start_of('day') + (
            duration(hours=10) + self.config.tick_length * self.current_tick
        )

    @property
    def balancing_markets(self):
        return {self._spot_market.time_slot: self.test_balancing_market}

    def get_balancing_market(self, time):
        return self.test_balancing_market

    @property
    def spot_market(self):
        return self._spot_market


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.id = count
        self.most_affordable_energy = 0.1551
        self.created_balancing_offers = []
        self.bids = {}
        self.in_sim_duration = True

    def get_bids(self):
        return deepcopy(self.bids)

    def bid(self, price: float, energy: float, buyer: str, original_price=None,
            time_slot=None) -> Bid:
        bid = Bid(id="bid_id", creation_time=now(), price=price, energy=energy,
                  buyer=buyer,
                  original_price=original_price,
                  time_slot=time_slot)
        self.bids[bid.id] = bid
        return bid

    @property
    def offers(self):
        return {
            o.id: o for o in self.sorted_offers
        }

    @property
    def sorted_offers(self):
        offers = [
            # Energy price is 1
            [Offer('id', now(), 1, (MIN_BUY_ENERGY/1000), TraderDetails("A", "")),
             # Energy price is 2
             Offer('id', now(), 2, (MIN_BUY_ENERGY/1000), TraderDetails("A", "")),
             # Energy price is 3
             Offer('id', now(), 3, (MIN_BUY_ENERGY/1000), TraderDetails("A", "")),
             # Energy price is 4
             Offer('id', now(), 4, (MIN_BUY_ENERGY/1000), TraderDetails("A", "")),
             ],
            [
                Offer('id', now(), 1, (MIN_BUY_ENERGY * 0.033 / 1000), TraderDetails("A", "")),
                Offer('id', now(), 2, (MIN_BUY_ENERGY * 0.033 / 1000), TraderDetails("A", ""))
            ],
            [
                Offer('id', now(), 1, 5, TraderDetails("A", "")),
                Offer('id2', now(), 2, (MIN_BUY_ENERGY / 1000), TraderDetails("A", ""))
            ]
        ]
        return offers[self.count]

    @property
    def most_affordable_offers(self):
        return [Offer('id_affordable', now(), 1,
                      self.most_affordable_energy, TraderDetails("A", ""))]

    @property
    def time_slot(self):
        return TIME

    @property
    def time_slot_str(self):
        return self.time_slot.strftime(TIME_FORMAT)

    def balancing_offer(self, price, energy, seller, market=None):
        offer = BalancingOffer('id', now(), price, energy, seller, market)
        self.created_balancing_offers.append(offer)
        offer.id = 'id'
        return offer

    def accept_offer(self, **kwargs):
        return Trade("", now(), TraderDetails("", ""), TraderDetails("", ""), 0.1, 0.1)


class TestLoadHoursStrategyInput(unittest.TestCase):

    def setUp(self):
        self.strategy1 = MagicMock(spec=LoadHoursStrategy)

    def tearDown(self):
        pass

    def area_test(self):
        area = FakeArea()
        area.current_market = FakeMarket(0)
        area.markets = {TIME: FakeMarket(0)}
        return area

    def Mock_LoadHoursStrategy(self, avg_power_W, hrs_per_day, hrs_of_day):
        strategy = LoadHoursStrategy(avg_power_W=avg_power_W,
                                     hrs_per_day=hrs_per_day,
                                     hrs_of_day=hrs_of_day)
        strategy.area = self.area_test()
        strategy.owner = self.area_test()
        strategy.event_activate()
        return strategy

    def test_LoadHoursStrategy_input(self):
        power_W = 620
        with self.assertRaises(GSyDeviceException):
            self.Mock_LoadHoursStrategy(power_W, 4, [1, 2])


@pytest.fixture()
def area_test1(market_test1):
    area = FakeArea()
    area.current_market = market_test1
    return area


@pytest.fixture
def area_test2(market_test2):
    area = FakeArea()
    area.current_market = market_test2
    area.markets = {TIME: market_test2}
    return area


@pytest.fixture()
def market_test1():
    return FakeMarket(0)


@pytest.fixture
def market_test2():
    return FakeMarket(2)


@pytest.fixture
def load_hours_strategy_test(called):
    strategy = LoadHoursStrategy(
        avg_power_W=620, hrs_per_day=4, hrs_of_day=[8, 9, 10, 12],
        initial_buying_rate=10)
    strategy.accept_offer = called
    return strategy


@pytest.fixture(name="load_hours_strategy_test1")
def fixture_load_hours_strategy_test1(load_hours_strategy_test, area_test1):
    load_hours_strategy_test.area = area_test1
    load_hours_strategy_test.owner = area_test1
    return load_hours_strategy_test


@pytest.fixture
def load_hours_strategy_test2(load_hours_strategy_test, area_test2):
    load_hours_strategy_test.area = area_test2
    load_hours_strategy_test.owner = area_test2
    return load_hours_strategy_test


@pytest.fixture
def load_hours_strategy_test4():
    strategy = LoadHoursStrategy(
        avg_power_W=620, hrs_per_day=4, hrs_of_day=[8, 9, 10, 12],
        initial_buying_rate=10)
    strategy.accept_offer = Mock()
    return strategy


@pytest.fixture
def load_hours_strategy_test5(load_hours_strategy_test4, area_test2):
    load_hours_strategy_test4.area = area_test2
    load_hours_strategy_test4.owner = area_test2
    return load_hours_strategy_test4


# Test if daily energy requirement is calculated correctly for the device
def test_activate_event_populates_energy_requirement(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    energy_requirement = load_hours_strategy_test1.state._energy_requirement_Wh
    assert all([energy == load_hours_strategy_test1._energy_params.energy_per_slot_Wh
                for energy in energy_requirement.values()])
    assert all([load_hours_strategy_test1.state._desired_energy_Wh[ts] == energy
                for ts, energy in energy_requirement.items()])


# Test if daily energy requirement is calculated correctly for the device
def test_calculate_daily_energy_req(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    assert all([energy == 620/4
                for energy in load_hours_strategy_test1.state._energy_requirement_Wh.values()])


# Test if device accepts the most affordable offer
def test_device_accepts_offer(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.event_market_cycle()
    cheapest_offer = market_test1.most_affordable_offers[0]
    load_hours_strategy_test1.state._energy_requirement_Wh = \
        {market_test1.time_slot: cheapest_offer.energy * 1000 + 1}
    load_hours_strategy_test1.event_tick()
    assert load_hours_strategy_test1.accept_offer.calls[0][0][1] == repr(cheapest_offer)


def test_active_markets(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    assert load_hours_strategy_test1.active_markets == \
        load_hours_strategy_test1.area.all_markets


def test_event_tick_updates_rates(load_hours_strategy_test1, market_test1):
    """The event_tick method invokes bids' rates updates correctly."""
    load_hours_strategy_test1.state.can_buy_more_energy = Mock()
    load_hours_strategy_test1.bid_update.update = Mock()
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.event_market_cycle()

    number_of_markets = len(load_hours_strategy_test1.area.all_markets)
    # Test for all available market types (one-sided and two-sided markets)
    available_market_types = (SpotMarketTypeEnum.ONE_SIDED.value,
                              SpotMarketTypeEnum.TWO_SIDED.value)
    # Bids' rates should be updated both when the load can buy energy and when it cannot do it
    for can_buy_energy in (True, False):
        load_hours_strategy_test1.state.can_buy_more_energy.return_value = can_buy_energy
        for market_type_id in available_market_types:
            ConstSettings.MASettings.MARKET_TYPE = market_type_id
            load_hours_strategy_test1.bid_update.update.reset_mock()

            load_hours_strategy_test1.event_tick()
            if market_type_id == 1:
                # Bids' rates are not updated in one-sided markets
                load_hours_strategy_test1.bid_update.update.assert_not_called()
            else:
                # Bids' rates are updated once for each market slot in two-sided markets
                assert load_hours_strategy_test1.bid_update.update.call_count == number_of_markets


def test_event_tick_one_sided_market_no_energy_required(load_hours_strategy_test1, market_test1):
    """
    The load does not make offers on tick events in one-sided markets when it cannot buy energy.
    """
    load_hours_strategy_test1.state.can_buy_more_energy = Mock(return_value=False)
    load_hours_strategy_test1.accept_offer = Mock()
    load_hours_strategy_test1.state.decrement_energy_requirement = Mock()

    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.event_tick()
    load_hours_strategy_test1.accept_offer.assert_not_called()
    load_hours_strategy_test1.state.decrement_energy_requirement.assert_not_called()


def test_event_tick_one_sided_market_energy_required(load_hours_strategy_test1, market_test1):
    """The load makes offers on tick events in one-sided markets when it can buy energy."""
    load_hours_strategy_test1.state.can_buy_more_energy = Mock(return_value=True)
    load_hours_strategy_test1.accept_offer = Mock()
    load_hours_strategy_test1.state.decrement_energy_requirement = Mock()

    load_hours_strategy_test1.event_activate()
    assert load_hours_strategy_test1._energy_params.hrs_per_day == {0: 4}
    load_hours_strategy_test1.event_market_cycle()
    load_hours_strategy_test1.event_tick()
    load_hours_strategy_test1.accept_offer.assert_called()
    load_hours_strategy_test1.state.decrement_energy_requirement.assert_called()
    # The amount of operating hours has decreased
    assert load_hours_strategy_test1._energy_params.hrs_per_day == {0: 3.25}


def test_event_tick(load_hours_strategy_test1, market_test1):
    market_test1.most_affordable_energy = 0.155
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    assert isclose(load_hours_strategy_test1.state._energy_requirement_Wh[TIME],
                   market_test1.most_affordable_energy * 1000)

    load_hours_strategy_test1.event_tick()
    assert load_hours_strategy_test1.state._energy_requirement_Wh[TIME] == 0


def test_event_tick_with_partial_offer(load_hours_strategy_test2, market_test2):
    market_test2.most_affordable_energy = 0.156
    load_hours_strategy_test2.event_activate()
    load_hours_strategy_test2.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test2.event_market_cycle()
    requirement = load_hours_strategy_test2.state._energy_requirement_Wh[TIME] / 1000
    load_hours_strategy_test2.event_tick()
    assert load_hours_strategy_test2.state._energy_requirement_Wh[TIME] == 0
    assert float(load_hours_strategy_test2.accept_offer.calls[0][1]['energy']) == requirement


def test_load_hours_constructor_rejects_incorrect_hrs_of_day():
    with pytest.raises(ValueError):
        LoadHoursStrategy(100, hrs_of_day=[12, 13, 24])


def test_device_operating_hours_deduction_with_partial_trade(load_hours_strategy_test5,
                                                             market_test2):
    market_test2.most_affordable_energy = 0.1
    load_hours_strategy_test5.event_activate()
    # load_hours_strategy_test5.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test5.event_market_cycle()
    load_hours_strategy_test5.event_tick()
    assert round(((
        float(load_hours_strategy_test5.accept_offer.call_args[0][1].energy) *
        1000 / load_hours_strategy_test5._energy_params.energy_per_slot_Wh) *
        (load_hours_strategy_test5.simulation_config.slot_length / duration(hours=1))), 2) == \
        round(((0.1/0.155) * 0.25), 2)


@pytest.mark.parametrize("partial", [None, Bid(
    'test_id', now(), 123, 321, TraderDetails("A", ""))])
def test_event_bid_traded_removes_bid_for_partial_and_non_trade(load_hours_strategy_test5,
                                                                called,
                                                                partial):
    ConstSettings.MASettings.MARKET_TYPE = 2

    trade_market = load_hours_strategy_test5.area.spot_market
    load_hours_strategy_test5.remove_bid_from_pending = called
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.area.markets = {TIME: trade_market}
    load_hours_strategy_test5.event_market_cycle()
    # Get the bid that was posted on event_market_cycle
    bid = list(load_hours_strategy_test5._bids.values())[0][0]

    # Increase energy requirement to cover the energy from the bid
    load_hours_strategy_test5.state._energy_requirement_Wh[TIME] = 1000
    trade = Trade('idt', None, TraderDetails("B", ""),
                  TraderDetails(load_hours_strategy_test5.owner.name, ""), bid=bid,
                  residual=partial, time_slot=TIME, traded_energy=1, trade_price=1)
    load_hours_strategy_test5.event_bid_traded(market_id=trade_market.id, bid_trade=trade)

    assert len(load_hours_strategy_test5.remove_bid_from_pending.calls) == 1
    assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][1] == repr(bid.id)
    assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][0] == \
        repr(trade_market.id)


def test_event_bid_traded_removes_bid_from_pending_if_energy_req_0(load_hours_strategy_test5,
                                                                   market_test2,
                                                                   called):
    ConstSettings.MASettings.MARKET_TYPE = 2

    trade_market = load_hours_strategy_test5.area.spot_market
    load_hours_strategy_test5.remove_bid_from_pending = called
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.area.markets = {TIME: trade_market}
    load_hours_strategy_test5.event_market_cycle()
    bid = list(load_hours_strategy_test5._bids.values())[0][0]
    # Increase energy requirement to cover the energy from the bid + threshold
    load_hours_strategy_test5.state._energy_requirement_Wh[TIME] = bid.energy * 1000 + 0.000009
    trade = Trade('idt', None, TraderDetails("B", ""),
                  TraderDetails(load_hours_strategy_test5.owner.name, ""), residual=True, bid=bid,
                  time_slot=TIME, traded_energy=bid.energy, trade_price=bid.price)
    load_hours_strategy_test5.event_bid_traded(market_id=trade_market.id, bid_trade=trade)

    assert len(load_hours_strategy_test5.remove_bid_from_pending.calls) == 1
    assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][1] == repr(bid.id)
    assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][0] == \
        repr(trade_market.id)


@pytest.fixture
def balancing_fixture(load_hours_strategy_test5):
    DeviceRegistry.REGISTRY = {
        "A": (23, 25),
        "someone": (23, 25),
        "seller": (23, 25),
        "FakeArea": (23, 25),
    }
    yield load_hours_strategy_test5
    DeviceRegistry.REGISTRY = {}


def test_balancing_offers_are_not_created_if_device_not_in_registry(
        balancing_fixture, area_test2):
    DeviceRegistry.REGISTRY = {}
    balancing_fixture.event_activate()
    balancing_fixture.event_market_cycle()
    assert len(area_test2.test_balancing_market.created_balancing_offers) == 0


def test_balancing_offers_are_created_if_device_in_registry(
        balancing_fixture, area_test2):
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    DeviceRegistry.REGISTRY = {'FakeArea': (30, 40)}
    balancing_fixture.event_activate()
    balancing_fixture.event_market_cycle()
    balancing_fixture.event_balancing_market_cycle()
    expected_balancing_demand_energy = \
        balancing_fixture.balancing_energy_ratio.demand * \
        balancing_fixture._energy_params.energy_per_slot_Wh
    actual_balancing_demand_energy = \
        area_test2.test_balancing_market.created_balancing_offers[0].energy
    assert len(area_test2.test_balancing_market.created_balancing_offers) == 1
    assert actual_balancing_demand_energy == -expected_balancing_demand_energy
    actual_balancing_demand_price = \
        area_test2.test_balancing_market.created_balancing_offers[0].price

    assert actual_balancing_demand_price == expected_balancing_demand_energy * 30
    selected_offer = area_test2.current_market.sorted_offers[0]
    balancing_fixture.state._energy_requirement_Wh[area_test2.current_market.time_slot] = \
        selected_offer.energy * 1000.0
    balancing_fixture.event_offer_traded(market_id=area_test2.current_market.id,
                                         trade=Trade(id='id',
                                                     creation_time=area_test2.now,
                                                     offer=selected_offer,
                                                     traded_energy=selected_offer.energy,
                                                     trade_price=selected_offer.price,
                                                     seller=TraderDetails("B", ""),
                                                     buyer=TraderDetails("FakeArea", ""),
                                                     time_slot=area_test2.current_market.time_slot)
                                         )
    assert len(area_test2.test_balancing_market.created_balancing_offers) == 2
    actual_balancing_supply_energy = \
        area_test2.test_balancing_market.created_balancing_offers[1].energy
    expected_balancing_supply_energy = \
        selected_offer.energy * balancing_fixture.balancing_energy_ratio.supply
    assert actual_balancing_supply_energy == expected_balancing_supply_energy
    actual_balancing_supply_price = \
        area_test2.test_balancing_market.created_balancing_offers[1].price
    assert actual_balancing_supply_price == expected_balancing_supply_energy * 40
    DeviceRegistry.REGISTRY = {}


@pytest.mark.parametrize("use_mmr, expected_rate", [
    [True, 9, ], [False, 33, ]
])
def test_use_market_maker_rate_parameter_is_respected(use_mmr, expected_rate):
    original_mmr = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = 9
    load = LoadHoursStrategy(200, final_buying_rate=33, use_market_maker_rate=use_mmr)
    load.area = FakeArea()
    load.owner = load.area
    load.event_activate()
    assert all(v == expected_rate for v in load.bid_update.final_rate.values())
    GlobalConfig.market_maker_rate = original_mmr


@pytest.mark.parametrize("use_mmr, expected_rate", [
    [True, 9, ], [False, 33, ]
])
def test_use_market_maker_rate_parameter_is_respected_for_load_profiles(use_mmr, expected_rate):
    original_mmr = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = 9
    user_profile_path = os.path.join(gsye_root_path, "resources/Solar_Curve_W_sunny.csv")
    load = DefinedLoadStrategy(
        daily_load_profile=user_profile_path,
        final_buying_rate=33,
        use_market_maker_rate=use_mmr)
    load.area = FakeArea()
    load.owner = load.area
    load.event_activate()
    assert all(v == expected_rate for v in load.bid_update.final_rate.values())
    GlobalConfig.market_maker_rate = original_mmr


def test_load_constructor_rejects_incorrect_rate_parameters():
    load = LoadHoursStrategy(avg_power_W=100, initial_buying_rate=10, final_buying_rate=5)
    load.area = FakeArea()
    load.owner = load.area
    with pytest.raises(GSyDeviceException):
        load.event_activate()
    with pytest.raises(GSyDeviceException):
        LoadHoursStrategy(avg_power_W=100, fit_to_limit=True,
                          energy_rate_increase_per_update=1)
    with pytest.raises(GSyDeviceException):
        LoadHoursStrategy(avg_power_W=100, fit_to_limit=False,
                          energy_rate_increase_per_update=-1)


def test_load_hour_strategy_increases_rate_when_fit_to_limit_is_false(market_test1):
    load = LoadHoursStrategy(avg_power_W=100, initial_buying_rate=0, final_buying_rate=30,
                             fit_to_limit=False, energy_rate_increase_per_update=10,
                             update_interval=5)
    load.area = FakeArea()
    load.owner = load.area
    load.event_activate()
    load.event_market_cycle()
    assert load.state._energy_requirement_Wh[TIME] == 25.0
    offer = Offer('id', now(), 1, (MIN_BUY_ENERGY/500), TraderDetails("A", ""), 1)
    load._one_sided_market_event_tick(market_test1, offer)
    assert load.bid_update.get_updated_rate(TIME) == 0
    assert load.state._energy_requirement_Wh[TIME] == 25.0
    load.event_tick()
    assert load.bid_update.get_updated_rate(TIME) == 10
    load._one_sided_market_event_tick(market_test1, offer)
    assert load.state._energy_requirement_Wh[TIME] == 0
    assert all([rate == -10 for rate in load.bid_update.energy_rate_change_per_update.values()])


@pytest.fixture
def load_hours_strategy_test3(area_test1):
    load = LoadHoursStrategy(avg_power_W=100)
    load.area = area_test1
    load.owner = area_test1
    return load


def test_assert_if_trade_rate_is_higher_than_bid_rate(load_hours_strategy_test3):
    market_id = 0
    load_hours_strategy_test3._bids[market_id] = \
        [Bid("bid_id", now(), 30, 1, buyer=TraderDetails("FakeArea", ""))]
    expensive_bid = Bid("bid_id", now(), 31, 1, buyer=TraderDetails("FakeArea", ""))
    trade = Trade("trade_id", "time", TraderDetails(load_hours_strategy_test3.owner.name, ""),
                  TraderDetails(load_hours_strategy_test3.owner.name, ""), bid=expensive_bid,
                  traded_energy=1, trade_price=31)

    with pytest.raises(AssertionError):
        load_hours_strategy_test3.event_offer_traded(market_id=market_id, trade=trade)


def test_event_market_cycle_updates_measurement_and_forecast(load_hours_strategy_test1):
    """update_state sends command to update the simulated real energy of the device."""
    load_hours_strategy_test1._set_energy_measurement_of_last_market = Mock()
    load_hours_strategy_test1._update_energy_requirement_in_state = Mock()
    load_hours_strategy_test1.event_market_cycle()
    load_hours_strategy_test1._set_energy_measurement_of_last_market.assert_called_once()
    load_hours_strategy_test1._update_energy_requirement_in_state.assert_called_once()


@patch("gsy_e.models.strategy.energy_parameters.load.utils")
def test_set_energy_measurement_of_last_market(utils_mock, load_hours_strategy_test1):
    """The real energy of the last market is set when necessary."""
    # If we are in the first market slot, the real energy is not set
    load_hours_strategy_test1.area.current_market = None
    load_hours_strategy_test1.state.set_energy_measurement_kWh = Mock()
    load_hours_strategy_test1._set_energy_measurement_of_last_market()
    load_hours_strategy_test1.state.set_energy_measurement_kWh.assert_not_called()

    # When there is at least one past market, the real energy is set
    load_hours_strategy_test1.state.set_energy_measurement_kWh.reset_mock()
    load_hours_strategy_test1.area.current_market = Mock()
    utils_mock.compute_altered_energy.return_value = 100

    load_hours_strategy_test1._set_energy_measurement_of_last_market()
    load_hours_strategy_test1.state.set_energy_measurement_kWh.assert_called_once_with(
        100, load_hours_strategy_test1.area.current_market.time_slot)


@pytest.mark.parametrize("use_mmr, initial_buying_rate", [
    (True, 40), (False, 40)])
def test_predefined_load_strategy_rejects_incorrect_rate_parameters(use_mmr, initial_buying_rate):
    user_profile_path = os.path.join(gsye_root_path, "resources/Solar_Curve_W_sunny.csv")
    load = DefinedLoadStrategy(
        daily_load_profile=user_profile_path,
        initial_buying_rate=initial_buying_rate,
        use_market_maker_rate=use_mmr)
    load.area = FakeArea()
    load.owner = load.area
    with pytest.raises(GSyDeviceException):
        load.event_activate()
    with pytest.raises(GSyDeviceException):
        DefinedLoadStrategy(daily_load_profile=user_profile_path, fit_to_limit=True,
                            energy_rate_increase_per_update=1)
    with pytest.raises(GSyDeviceException):
        DefinedLoadStrategy(daily_load_profile=user_profile_path, fit_to_limit=False,
                            energy_rate_increase_per_update=-1)


@pytest.fixture(name="load_hours_fixture")
def load_hours_for_settlement_tests(area_test1: Area) -> LoadHoursStrategy:
    """Return LoadHoursStrategy object for testing of the interaction with settlement market."""
    orig_market_type = ConstSettings.MASettings.MARKET_TYPE
    ConstSettings.MASettings.MARKET_TYPE = 2
    load = LoadHoursStrategy(avg_power_W=100)
    area = FakeArea()
    load.area = area
    load.owner = area
    yield load
    ConstSettings.MASettings.MARKET_TYPE = orig_market_type


def test_event_bid_traded_calls_settlement_market_event_bid_traded(load_hours_fixture):
    """Test if _settlement_market_strategy.event_bid_traded was called
    although no spot market can be found by event_bid_traded."""
    load_hours_fixture._settlement_market_strategy = Mock()
    bid = Bid("bid", None, 1, 1, TraderDetails("buyer", ""))
    trade = Trade('idt', None, TraderDetails("B", ""),
                  TraderDetails(load_hours_fixture.owner.name, ""), bid=bid,
                  traded_energy=1, trade_price=1)
    load_hours_fixture.event_bid_traded(market_id="not existing", bid_trade=trade)
    load_hours_fixture._settlement_market_strategy.event_bid_traded.assert_called_once()


def test_event_offer_traded_calls_settlement_market_event_offer_traded(load_hours_fixture):
    """Test if _settlement_market_strategy.event_offer_traded was called
    although no spot market can be found by event_offer_traded."""
    load_hours_fixture._settlement_market_strategy = Mock()
    offer = Offer("oid", None, 1, 1, TraderDetails("seller", ""))
    trade = Trade('idt', None, TraderDetails("B", ""),
                  TraderDetails(load_hours_fixture.owner.name, ""), offer=offer,
                  traded_energy=1, trade_price=1)
    load_hours_fixture.event_offer_traded(market_id="not existing", trade=trade)
    load_hours_fixture._settlement_market_strategy.event_offer_traded.assert_called_once()
