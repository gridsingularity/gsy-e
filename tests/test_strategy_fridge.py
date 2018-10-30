import pytest
from unittest.mock import Mock

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.fridge import FridgeStrategy


class FakeCurrentMarket:
    def __init__(self, time_slot):
        self.time_slot = time_slot


class FakeArea:
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.stats = Mock()
        self.stats.historical_min_max_price = self.historical_min_max_price
        self.stats.historical_avg_rate = self.historical_avg_rate

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def current_tick(self):
        return 5

    @property
    def historical_avg_rate(self):
        avg_price = [30]
        return avg_price[self.count]

    @property
    def historical_min_max_price(self):
        min_max = [(30, 30)]
        return min_max[self.count]

    @property
    def current_market(self):
        return FakeCurrentMarket("00:00:00")


class FakeMarket:
    def __init__(self, count):
        self.count = count

    @property
    def sorted_offers(self):
        offers = [
            [Offer('id', (10 * (ConstSettings.FridgeSettings.MIN_NEEDED_ENERGY / 1000)),
                   (ConstSettings.FridgeSettings.MIN_NEEDED_ENERGY / 1000), 'A', self
                   )
             ],
            [Offer('id', 100000000,
                   (ConstSettings.FridgeSettings.MIN_NEEDED_ENERGY / 1000), 'A', self
                   )
             ],
            [Offer('id', (30 * (ConstSettings.FridgeSettings.MIN_NEEDED_ENERGY / 1000)),
                   (ConstSettings.FridgeSettings.MIN_NEEDED_ENERGY / 1000), 'A', self
                   )
             ],
            [

             ],
            [Offer('id', 10 * 50 * ConstSettings.FridgeSettings.MIN_NEEDED_ENERGY,
                   50 * ConstSettings.FridgeSettings.MIN_NEEDED_ENERGY, 'A', self)]
        ]
        return offers[self.count]


"""TEST1"""


# Testing if fridge accepts an offer he should accept

@pytest.fixture
def market_test1():
    return FakeMarket(0)


@pytest.fixture
def area_test1():
    return FakeArea(0)


@pytest.fixture
def fridge_strategy_test1(market_test1, area_test1, called):
    f = FridgeStrategy()
    f.owner = area_test1
    f.area = area_test1
    f.area.all_markets = [market_test1]
    f.open_spot_markets = [market_test1]
    f.accept_offer = called

    return f


def test_if_fridge_accepts_valid_offer(fridge_strategy_test1, area_test1, market_test1):
    fridge_strategy_test1.event_activate()
    fridge_strategy_test1.event_tick(area=area_test1)
    assert fridge_strategy_test1.accept_offer.calls[0][0][1] == repr(market_test1.sorted_offers[0])


"""TEST2"""


# Testing if fridge doesn't accept offer if he is cold enough

@pytest.fixture
def market_test2():
    return FakeMarket(0)


@pytest.fixture
def area_test2():
    return FakeArea(0)


@pytest.fixture
def fridge_strategy_test2(market_test2, area_test2, called):
    f = FridgeStrategy()
    f.owner = area_test2
    f.area = area_test2
    f.area.all_markets = [market_test2]
    f.state.temperature = 4
    f.accept_offer = called
    return f


def test_if_fridge_cools_too_much(fridge_strategy_test2, area_test2, market_test2):
    fridge_strategy_test2.event_activate()
    fridge_strategy_test2.event_tick(area=area_test2)
    assert len(fridge_strategy_test2.accept_offer.calls) == 0


"""TEST3"""


# Testing if fridge accepts every offer if he is too warm

@pytest.fixture
def market_test3():
    return FakeMarket(0)


@pytest.fixture
def area_test3():
    return FakeArea(0)


@pytest.fixture
def fridge_strategy_test3(market_test3, area_test3, called):
    f = FridgeStrategy()
    f.owner = area_test3
    f.area = area_test3
    f.state.temperature = 7.9
    f.area.all_markets = [market_test3]
    f.accept_offer = called
    return f


def test_if_warm_fridge_buys(fridge_strategy_test3, area_test3, market_test3):
    fridge_strategy_test3.event_activate()
    fridge_strategy_test3.event_tick(area=area_test3)
    assert fridge_strategy_test3.accept_offer.calls[0][0][1] == repr(market_test3.sorted_offers[0])


# TEST4 is obsolete
"""TEST5"""


# Testing if market cycle works correct


def test_if_fridge_market_cycles(fridge_strategy_test1, area_test1, market_test1):
    fridge_strategy_test1.event_market_cycle()
    assert fridge_strategy_test1.temp_history["00:00:00"] == 6.0


"""TEST6"""


# Testing if bought energy cools the fridge for the right amount


def test_if_fridge_temperature_decreases_correct(fridge_strategy_test1, area_test1, market_test1):
    fridge_strategy_test1.event_tick(area=area_test1)
    # 6.0 = start fridge temp, 0.05*2 = cooling_temperature, tick_length... = warming per tick
    assert fridge_strategy_test1.fridge_temp == ((6.0 - (0.05 * 2))
                                                 + (area_test1.config.tick_length.in_seconds()
                                                    * round((0.02 / 60), 6)
                                                    )
                                                 )


@pytest.fixture
def market_test4():
    return FakeMarket(2)


@pytest.fixture
def area_test4():
    return FakeArea(0)


@pytest.fixture
def fridge_strategy_test4(market_test4, area_test4, called):
    f = FridgeStrategy()
    f.owner = area_test4
    f.area = area_test4
    f.area.all_markets = [market_test4]
    f.accept_offer = called
    return f


def test_offer_price_greater_than_threshold(fridge_strategy_test4, area_test4, market_test4):
    fridge_strategy_test4.event_activate()
    cheapest_offer = list(market_test4.sorted_offers)[-1]
    fridge_strategy_test4.event_tick(area=area_test4)
    assert (cheapest_offer.price / cheapest_offer.energy) > fridge_strategy_test4.threshold_price


@pytest.fixture
def market_test5():
    return FakeMarket(3)


@pytest.fixture
def area_test5():
    return FakeArea(0)


@pytest.fixture
def fridge_strategy_test5(market_test5, area_test5, called):
    f = FridgeStrategy()
    f.next_market = market_test5
    f.owner = area_test5
    f.area = area_test5
    f.area.all_markets = [market_test5]
    f.accept_offer = called
    return f


def test_no_offers_left(fridge_strategy_test5, area_test5, market_test5):
    fridge_strategy_test5.event_activate()
    fridge_strategy_test5.event_tick(area=area_test5)
    # FIXME


def test_frigde_buys_partial_offer(area_test5, called):
    fridge = FridgeStrategy()
    market = FakeMarket(4)
    fridge.area = area_test5
    fridge.open_spot_markets = [market]
    fridge.accept_offer = called
    fridge.event_tick(area=area_test5)
    assert float(fridge.accept_offer.calls[0][1]['energy']) > 0


def test_heatpump_constructor_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        FridgeStrategy(risk=-1)
    with pytest.raises(ValueError):
        FridgeStrategy(risk=101)
