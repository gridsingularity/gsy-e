import pytest

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market.market_structures import Offer
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.heatpump import HeatPumpStrategy


class FakeArea():
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count
        self.current_market = FakeMarket(0)

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
    def markets(self):
        return {'next market': self.current_market}


class FakeMarket:
    def __init__(self, count):
        self.count = count

    @property
    def sorted_offers(self):
        offers = [
            [Offer('id', (10 * (ConstSettings.HeatpumpSettings.MIN_NEEDED_ENERGY / 1000)),
                   (ConstSettings.HeatpumpSettings.MIN_NEEDED_ENERGY / 1000), 'A', self
                   )
             ],
            [Offer('id', 100000000,
                   (ConstSettings.HeatpumpSettings.MIN_NEEDED_ENERGY / 1000), 'A', self
                   )
             ]
        ]
        return offers[self.count]


"""TEST1"""


# Testing event tick for heatpump


@pytest.fixture
def area_test1():
    return FakeArea(0)


@pytest.fixture
def heatpump_strategy_test1(area_test1, called):
    h = HeatPumpStrategy()
    h.next_market = area_test1.current_market
    h.owner = area_test1
    h.area = area_test1
    h.accept_offer = called
    return h


# Testing if heatpump buy acceptable offer
# Strategy is cloned from fridge
def test_event_tick(heatpump_strategy_test1, area_test1):
    heatpump_strategy_test1.event_tick(area=area_test1)
    assert (heatpump_strategy_test1.accept_offer.calls[0][0][1] ==
            repr(area_test1.current_market.sorted_offers[0])
            )


def test_heatpump_constructor_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        HeatPumpStrategy(risk=-1)
    with pytest.raises(ValueError):
        HeatPumpStrategy(risk=101)
