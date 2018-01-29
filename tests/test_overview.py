import pytest
import requests_mock

from d3a.models.area import DEFAULT_CONFIG
from d3a.models.events import AreaEvent
from d3a.models.overview import Overview


class FakeMarket:
    def __init__(self):
        self.avg_trade_price = 10
        self.avg_offer_price = 8
        self.actual_energy_agg = {}


class FakeArea:
    def __init__(self):
        self.current_tick = 0
        self.current_slot = 1

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def current_market(self):
        return FakeMarket()

    def add_listener(self, listener):
        self.listener = listener

    ticks_per_slot = DEFAULT_CONFIG.slot_length / DEFAULT_CONFIG.tick_length


class FakeSimulation:
    def __init__(self):
        self.finished = False
        self.area = FakeArea()


@pytest.fixture
def fixture():
    simulation = FakeSimulation()
    simulation.area.current_tick = FakeArea.ticks_per_slot
    return Overview(simulation, "ws://mock.com")


@pytest.mark.skip("Needs fixing")
def test_overview_sends(fixture):
    with requests_mock.Mocker() as mocker:
        mocker.post("http://mock.com")
        fixture.event_listener(AreaEvent.TICK)
        assert mocker.call_count == 1
        assert mocker.request_history[0].json()['avg-trade-price'] == 10


@pytest.mark.skip("Needs fixing")
def test_overview_ignores_other_events(fixture):
    with requests_mock.Mocker() as mocker:
        mocker.post("http://mock.com")
        fixture.event_listener(AreaEvent.ACTIVATE)
        fixture.area.current_tick = 1
        fixture.event_listener(AreaEvent.TICK)
        assert mocker.call_count == 0
