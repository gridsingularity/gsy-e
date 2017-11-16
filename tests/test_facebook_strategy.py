import pytest
import pendulum
from pendulum import Pendulum

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market import Offer
from d3a.models.strategy.facebook_device import FacebookDeviceStrategy

TIME = pendulum.today().at(hour=10, minute=45, second=2)

MIN_BUY_ENERGY = 50  # wh


class FakeArea:
    def __init__(self, count):
        self.appliance = None
        self.name = 'FakeArea'
        self.count = count

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def current_tick(self):
        return 5

    @property
    def now(self) -> Pendulum:
        """
        Return the 'current time' as a `Pendulum` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return Pendulum.now().start_of('day').add_timedelta(
            self.config.tick_length * self.current_tick
        )


class FakeMarket:
    def __init__(self, count):
        self.count = count

    @property
    def sorted_offers(self):
        offers = [
            Offer('id', 1, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 1
            Offer('id', 2, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 2
            Offer('id', 3, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 3
            Offer('id', 4, (MIN_BUY_ENERGY/1000), 'A', self),  # Energyprice is 4
        ]
        return offers


@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def market_test1():
    return FakeMarket(0)


@pytest.fixture()
def facebook_strategy_test1(area_test1, market_test1, called):
    fb = FacebookDeviceStrategy(avg_power=620, hrs_per_day=4)
    fb.owner = area_test1
    fb.area = area_test1
    fb.area.markets = {'next_market': market_test1}
    fb.accept_offer = called
    return fb


# Test if daily energy requirement is calculated correctly for the device
def test_calculate_daily_energy_req(facebook_strategy_test1, market_test1):
    facebook_strategy_test1.event_activate()
    facebook_strategy_test1.daily_energy_required = 620*4


# Test if device accepts the cheapest offer
def test_device_accepts_offer(facebook_strategy_test1, market_test1):
    facebook_strategy_test1.event_activate()
    facebook_strategy_test1.event_tick(area=area_test1)
    assert facebook_strategy_test1.accept_offer.calls[0][0][1] == \
        repr(market_test1.sorted_offers[0])
    for time, value in facebook_strategy_test1.energy_consumed.items():
        assert value == 50
