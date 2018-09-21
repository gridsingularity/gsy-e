import pytest
import unittest
import pendulum
from unittest.mock import MagicMock, Mock
from datetime import timedelta
from pendulum import DateTime
from pendulum import duration
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.market import Bid, Trade
from d3a import TIME_FORMAT

TIME = pendulum.today().at(hour=10, minute=45, second=2)

MIN_BUY_ENERGY = 50  # wh


class FakeArea:
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self._next_market = FakeMarket(15)

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
        return DateTime.now().start_of('day') + (
            timedelta(hours=10) + self.config.tick_length * self.current_tick
        )

    @property
    def next_market(self):
        return self._next_market


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.most_affordable_energy = 0.1551

    def bid(self, price: float, energy: float, buyer: str, seller: str):
        return Bid(id='bid_id', price=price, energy=energy, buyer=buyer, seller=seller)

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
        return DateTime.now().start_of('day') + timedelta(hours=10)

    @property
    def time_slot_str(self):
        return self.time_slot.strftime(TIME_FORMAT)


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
        self.assertEqual(
            self.Mock_LoadHoursStrategy(
                power_W, 4, [1, 2, 3, 4]).daily_energy_required,  power_W * 4)
        self.assertEqual(
            self.Mock_LoadHoursStrategy(
                power_W, None, [1, 2, 3, 4]).daily_energy_required, power_W * 4)
        self.assertEqual(
            self.Mock_LoadHoursStrategy(
                power_W, 4, [1, 2, 3, 4, 5, 6]).daily_energy_required, power_W * 4)
        self.assertEqual(
            self.Mock_LoadHoursStrategy(
                power_W, 4, None).daily_energy_required, power_W * 4)
        with self.assertRaises(ValueError):
            self.Mock_LoadHoursStrategy(power_W, 4, [1, 2])


@pytest.fixture()
def area_test1(market_test1):
    area = FakeArea(0)
    area.current_market = market_test1
    area.markets = {TIME: market_test1}
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
    strategy.accept_offer.call_args
    return strategy


@pytest.fixture
def load_hours_strategy_test5(load_hours_strategy_test4, area_test2):
    load_hours_strategy_test4.area = area_test2
    load_hours_strategy_test4.owner = area_test2
    return load_hours_strategy_test4


# Test if daily energy requirement is calculated correctly for the device
def test_calculate_daily_energy_req(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    assert load_hours_strategy_test1.daily_energy_required == 620*4


# Test if daily energy requirement is calculated correctly for the device
def test_activate_event_populates_energy_requirement(load_hours_strategy_test1):
    load_hours_strategy_test1.event_activate()
    assert load_hours_strategy_test1.energy_requirement_Wh == \
        load_hours_strategy_test1.energy_per_slot_Wh
    ts = load_hours_strategy_test1.area.next_market.time_slot
    assert load_hours_strategy_test1.state.desired_energy[ts] == \
        load_hours_strategy_test1.energy_requirement_Wh


# Test if device accepts the most affordable offer
def test_device_accepts_offer(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    cheapest_offer = market_test1.most_affordable_offers[0]
    load_hours_strategy_test1.energy_requirement_Wh = cheapest_offer.energy * 1000 + 1
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.accept_offer.calls[0][0][1] == repr(cheapest_offer)


def test_event_market_cycle(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement_Wh == \
        load_hours_strategy_test1.energy_per_slot_Wh


def test_event_market_cycle_resets_energy_requirement(load_hours_strategy_test1, market_test1):
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.energy_requirement_Wh = 150.0
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement_Wh == \
        load_hours_strategy_test1.energy_per_slot_Wh
    load_hours_strategy_test1.energy_requirement_Wh += 1000000.0
    load_hours_strategy_test1.event_market_cycle()
    assert load_hours_strategy_test1.energy_requirement_Wh == \
        load_hours_strategy_test1.energy_per_slot_Wh


def test_event_tick(load_hours_strategy_test1, market_test1):
    market_test1.most_affordable_energy = 0.155
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.energy_requirement_Wh == 0
    market_test1.most_affordable_energy = 0.154
    load_hours_strategy_test1.event_activate()
    load_hours_strategy_test1.area.past_markets = {TIME: market_test1}
    load_hours_strategy_test1.event_market_cycle()
    load_hours_strategy_test1.event_tick(area=area_test1)
    assert load_hours_strategy_test1.energy_requirement_Wh == 0.001 * 1000.0


def test_event_tick_with_partial_offer(load_hours_strategy_test2, market_test2):
    market_test2.most_affordable_energy = 0.156
    load_hours_strategy_test2.event_activate()
    load_hours_strategy_test2.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test2.event_market_cycle()
    requirement = load_hours_strategy_test2.energy_requirement_Wh / 1000
    load_hours_strategy_test2.event_tick(area=area_test2)
    assert load_hours_strategy_test2.energy_requirement_Wh == 0
    assert float(load_hours_strategy_test2.accept_offer.calls[0][1]['energy']) == requirement


def test_load_hours_constructor_rejects_incorrect_hrs_of_day():
    with pytest.raises(ValueError):
        LoadHoursStrategy(100, hrs_of_day=[12, 13, 24])


def test_device_operating_hours_deduction_with_partial_trade(load_hours_strategy_test5,
                                                             market_test2):
    market_test2.most_affordable_energy = 0.1
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test5.event_market_cycle()
    load_hours_strategy_test5.event_tick(area=area_test2)
    assert round(((float(load_hours_strategy_test5.accept_offer.call_args[0][1].energy) *
                   1000 / load_hours_strategy_test5.energy_per_slot_Wh) *
                  (load_hours_strategy_test5.area.config.slot_length / duration(hours=1))), 2) == \
        round(((0.1/0.155) * 0.25), 2)


@pytest.mark.parametrize("partial", [False, True])
def test_event_bid_traded_does_not_remove_bid_for_partial_trade(load_hours_strategy_test5,
                                                                market_test2,
                                                                called,
                                                                partial):
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2

    trade_market = load_hours_strategy_test5.area.next_market
    load_hours_strategy_test5.remove_bid_from_pending = called
    load_hours_strategy_test5.event_activate()
    load_hours_strategy_test5.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test5.event_market_cycle()
    load_hours_strategy_test5.event_tick(area=area_test2)
    # Get the bid that was posted on event_market_cycle
    bid = list(load_hours_strategy_test5._bids.values())[0][0]

    # Increase energy requirement to cover the energy from the bid
    load_hours_strategy_test5.energy_requirement_Wh = 1000
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
    load_hours_strategy_test5.area.past_markets = {TIME: market_test2}
    load_hours_strategy_test5.event_market_cycle()
    load_hours_strategy_test5.event_tick(area=area_test2)
    bid = list(load_hours_strategy_test5._bids.values())[0][0]

    # Increase energy requirement to cover the energy from the bid + threshold
    load_hours_strategy_test5.energy_requirement_Wh = bid.energy * 1000 + 0.000009
    trade = Trade('idt', None, bid, 'B', load_hours_strategy_test5.owner.name, residual=True)
    load_hours_strategy_test5.event_bid_traded(market=trade_market, bid_trade=trade)

    assert len(load_hours_strategy_test5.remove_bid_from_pending.calls) == 1
    assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][0] == repr(bid.id)
    assert load_hours_strategy_test5.remove_bid_from_pending.calls[0][0][1] == \
        repr(trade_market)

    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 1
