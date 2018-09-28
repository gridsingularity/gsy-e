import pytest
import unittest
import pendulum
from unittest.mock import MagicMock, Mock
from datetime import timedelta
from pendulum import DateTime
from pendulum import duration
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer, BalancingOffer
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.market import Bid, Trade
from d3a import TIME_FORMAT
from d3a import TIME_ZONE
from d3a.device_registry import DeviceRegistry

DeviceRegistry.REGISTRY = {
    "A": (23, 25),
    "someone": (23, 25),
    "seller": (23, 25),
    "FakeArea": (23, 25),
}

ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH = 10

TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=5)

MIN_BUY_ENERGY = 50  # wh


class FakeArea:
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count

        self._next_market = FakeMarket(0)
        self._bids = {}
        self.markets = {TIME: FakeMarket(0),
                        TIME + self.config.slot_length: FakeMarket(0),
                        TIME + 2 * self.config.slot_length: FakeMarket(0)}
        self.test_balancing_market = FakeMarket(1)
        self.test_balancing_market_2 = FakeMarket(2)

    @property
    def config(self):
        return DEFAULT_CONFIG

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
            timedelta(hours=10) + self.config.tick_length * self.current_tick
        )

    @property
    def balancing_markets(self):
        return {self._next_market.time_slot: self.test_balancing_market}

    @property
    def next_market(self):
        return self._next_market


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.most_affordable_energy = 0.1551
        self.created_balancing_offers = []
        self.bids = {}

    def bid(self, price: float, energy: float, buyer: str, seller: str, bid_id: str=None) -> Bid:
        bid = Bid(id='bid_id', price=price, energy=energy, buyer=buyer, seller=seller)
        self.bids[bid.id] = bid
        return bid

    @property
    def sorted_offers(self):
        offers = [
            [
                Offer('id', 1, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 1
                Offer('id', 2, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 2
                Offer('id', 3, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 3
                Offer('id', 4, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 4
            ],
            [
                Offer('id', 1, (MIN_BUY_ENERGY * 0.033 / 1000), 'A', self),
                Offer('id', 2, (MIN_BUY_ENERGY * 0.033 / 1000), 'A', self)
            ],
            [
                Offer('id', 1, 5, 'A', self),
                Offer('id2', 2, (MIN_BUY_ENERGY / 1000), 'A', self)
            ]
        ]
        return offers[self.count]

    @property
    def most_affordable_offers(self):
        return [Offer('id_affordable', 1, self.most_affordable_energy, 'A', self)]

    @property
    def time_slot(self):
        return TIME

    @property
    def time_slot_str(self):
        return self.time_slot.strftime(TIME_FORMAT)

    def balancing_offer(self, price, energy, seller, market=None):
        offer = BalancingOffer('id', price, energy, seller, market)
        self.created_balancing_offers.append(offer)
        offer.id = 'id'
        return offer


class TestLoadHoursStrategyInput(unittest.TestCase):

    def setUp(self):
        # MAX_OFFER_TRAVERSAL_LENGTH should be set here, otherwise some tests fail
        # when only the load tests are executed. Works fine when all tests are executed
        # though
        ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH = 5
        self.appliance = MagicMock(spec=SimpleAppliance)
        self.strategy1 = MagicMock(spec=LoadHoursStrategy)

    def tearDown(self):
        pass

    def area_test(self):
        area = FakeArea(0)
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
        with self.assertRaises(ValueError):
            self.Mock_LoadHoursStrategy(power_W, 4, [1, 2])


@pytest.fixture()
def area_test1(market_test1):
    area = FakeArea(0)
    area.current_market = market_test1
    return area


@pytest.fixture
def area_test2(market_test2):
    area = FakeArea(0)
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
    strategy = LoadHoursStrategy(avg_power_W=620, hrs_per_day=4, hrs_of_day=[8, 9, 10, 12])
    strategy.accept_offer = called
    return strategy


@pytest.fixture
def load_hours_strategy_test1(load_hours_strategy_test, area_test1):
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
    strategy = LoadHoursStrategy(avg_power_W=620, hrs_per_day=4, hrs_of_day=[8, 9, 10, 12])
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
    assert all([energy == load_hours_strategy_test1.energy_per_slot_Wh
                for energy in load_hours_strategy_test1.energy_requirement_Wh.values()])
    assert all([load_hours_strategy_test1.state.desired_energy_Wh[ts] == energy
                for ts, energy in load_hours_strategy_test1.energy_requirement_Wh.items()])


# Test if daily energy requirement is calculated correctly for the device
def test_calculate_daily_energy_req(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    assert all([energy == 620/4
                for energy in load_hours_strategy_test1.energy_requirement_Wh.values()])


# Test if device accepts the most affordable offer
def test_device_accepts_offer(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    cheapest_offer = market_test1.most_affordable_offers[0]
    load_hours_strategy_test1.energy_requirement_Wh = \
        {market_test1.time_slot: cheapest_offer.energy * 1000 + 1}
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.accept_offer.calls[0][0][1] == repr(cheapest_offer)


def test_active_markets(load_hours_strategy_test1):
    assert load_hours_strategy_test1.active_markets == \
           [list(load_hours_strategy_test1.area.markets.values())[0]]


def test_event_tick(load_hours_strategy_test1, market_test1):
    market_test1.most_affordable_energy = 0.155
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement_Wh[TIME] == \
        market_test1.most_affordable_energy * 1000
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.energy_requirement_Wh[TIME] == 0


def test_event_tick_with_partial_offer(load_hours_strategy_test2, market_test2):
    market_test2.most_affordable_energy = 0.156
    load_hours_strategy_test2.event_activate()
    load_hours_strategy_test2.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test2.event_market_cycle()
    requirement = load_hours_strategy_test2.energy_requirement_Wh[TIME] / 1000
    load_hours_strategy_test2.event_tick(area=area_test2)
    assert load_hours_strategy_test2.energy_requirement_Wh[TIME] == 0
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
    load_hours_strategy_test5.event_tick(area=area_test2)
    assert round(((float(load_hours_strategy_test5.accept_offer.call_args[0][1].energy) *
                   1000 / load_hours_strategy_test5.energy_per_slot_Wh) *
                  (load_hours_strategy_test5.area.config.slot_length / duration(hours=1))), 2) == \
        round(((0.1/0.155) * 0.25), 2)


@pytest.mark.parametrize("partial", [False, True])
def test_event_bid_traded_does_not_remove_bid_for_partial_trade(load_hours_strategy_test5,
                                                                called,
                                                                partial):
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2

    trade_market = load_hours_strategy_test5.area.next_market
    load_hours_strategy_test5.remove_bid_from_pending = called
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.area.markets = {TIME: trade_market}
    load_hours_strategy_test5.event_market_cycle()
    load_hours_strategy_test5.event_tick(area=area_test2)
    # Get the bid that was posted on event_market_cycle
    bid = list(load_hours_strategy_test5._bids.values())[0][0]

    # Increase energy requirement to cover the energy from the bid
    load_hours_strategy_test5.energy_requirement_Wh[TIME] = 1000
    trade = Trade('idt', None, bid, 'B', load_hours_strategy_test5.owner.name, residual=partial)
    load_hours_strategy_test5.event_bid_traded(market=trade_market, bid_trade=trade)

    if not partial:
        assert len(load_hours_strategy_test5.remove_bid_from_pending.calls) == 1
        assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][0] == repr(bid.id)
        assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][1] == \
            repr(trade_market)
    else:
        assert len(load_hours_strategy_test5.remove_bid_from_pending.calls) == 0
        assert load_hours_strategy_test5.get_posted_bids(trade_market) == [bid]

    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 1


def test_event_bid_traded_removes_bid_from_pending_if_energy_req_0(load_hours_strategy_test5,
                                                                   market_test2,
                                                                   called):
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2

    trade_market = load_hours_strategy_test5.area.next_market
    load_hours_strategy_test5.remove_bid_from_pending = called
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.area.markets = {TIME: trade_market}
    load_hours_strategy_test5.event_market_cycle()
    load_hours_strategy_test5.event_tick(area=area_test2)
    bid = list(load_hours_strategy_test5._bids.values())[0][0]
    # Increase energy requirement to cover the energy from the bid + threshold
    load_hours_strategy_test5.energy_requirement_Wh[TIME] = bid.energy * 1000 + 0.000009
    trade = Trade('idt', None, bid, 'B', load_hours_strategy_test5.owner.name, residual=True)
    load_hours_strategy_test5.event_bid_traded(market=trade_market, bid_trade=trade)

    assert len(load_hours_strategy_test5.remove_bid_from_pending.calls) == 1
    assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][0] == repr(bid.id)
    assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][1] == \
        repr(trade_market)

    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 1


def test_balancing_offers_are_not_created_if_device_not_in_registry(
        load_hours_strategy_test5, area_test2):
    DeviceRegistry.REGISTRY = {}
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.event_market_cycle()
    assert len(area_test2.test_balancing_market.created_balancing_offers) == 0


def test_balancing_offers_are_created_if_device_in_registry(
        load_hours_strategy_test5, area_test2):
    DeviceRegistry.REGISTRY = {'FakeArea': (30, 40)}
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.event_market_cycle()
    expected_balancing_demand_energy =\
        load_hours_strategy_test5.balancing_energy_ratio.demand * \
        load_hours_strategy_test5.energy_per_slot_Wh / 1000
    actual_balancing_demand_energy = \
        area_test2.test_balancing_market.created_balancing_offers[0].energy
    assert len(area_test2.test_balancing_market.created_balancing_offers) == 1
    assert actual_balancing_demand_energy == -expected_balancing_demand_energy
    actual_balancing_demand_price = \
        area_test2.test_balancing_market.created_balancing_offers[0].price

    assert actual_balancing_demand_price == expected_balancing_demand_energy * 30
    selected_offer = area_test2.current_market.sorted_offers[0]
    load_hours_strategy_test5.event_trade(market=area_test2.current_market,
                                          trade=Trade(id='id',
                                                      time=area_test2.now,
                                                      offer=selected_offer,
                                                      seller='B',
                                                      buyer='FakeArea'))
    assert len(area_test2.test_balancing_market.created_balancing_offers) == 2
    actual_balancing_supply_energy = \
        area_test2.test_balancing_market.created_balancing_offers[1].energy
    expected_balancing_supply_energy = \
        selected_offer.energy * load_hours_strategy_test5.balancing_energy_ratio.supply
    assert actual_balancing_supply_energy == expected_balancing_supply_energy
    actual_balancing_supply_price = \
        area_test2.test_balancing_market.created_balancing_offers[1].price
    assert actual_balancing_supply_price == expected_balancing_supply_energy * 40
    DeviceRegistry.REGISTRY = {}
